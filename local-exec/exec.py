#!/usr/bin/env python3
"""
Local Exec
安全命令执行器
允许 LLM 在受控环境中执行本地命令，包含多重安全机制
"""

import os
import sys
import json
import yaml
import logging
import argparse
import subprocess
import shlex
import re
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import fnmatch


@dataclass
class CommandRecord:
    """命令执行记录"""
    id: str
    timestamp: str
    command: str
    params: Dict[str, Any]
    user: str
    permission_level: str
    status: str  # success, failed, denied
    output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    confirm_required: bool = False
    confirmed: bool = False


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    command: str
    error_message: Optional[str] = None


class CommandExecutor:
    """命令执行器"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "config.yaml")
        self.config = self._load_config()
        self.logger = self._setup_logging()
        
        # 加载命令白名单
        self.commands = self.config.get("commands", {})
        self.templates = self.config.get("templates", {})
        
        # 当前权限级别
        self.permission_level = self.config.get("permission_level", "readonly")
        
        # 执行记录
        self.history_file = self._get_history_file()
        self.command_history = self._load_history()
        
        # 缓存
        self.cache_enabled = self.config.get("cache", {}).get("enabled", False)
        self.cache_dir = self._get_cache_dir()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 展开路径
        if 'security' in config and 'log_file' in config['security']:
            config['security']['log_file'] = os.path.expanduser(config['security']['log_file'])
        
        return config
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get("logging", {})
        
        logger = logging.getLogger("exec")
        logger.setLevel(getattr(logging, log_config.get("level", "INFO").upper()))
        
        # 日志处理器
        handler = logging.StreamHandler()
        formatter = logging.Formatter(log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # 文件日志
        log_file = log_config.get("file")
        if log_file:
            log_path = Path(os.path.expanduser(log_file))
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            if log_config.get("rotation", {}).get("enabled", False):
                from logging.handlers import RotatingFileHandler
                max_size = log_config["rotation"].get("max_size", "10MB")
                
                # 转换大小
                size_units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
                import re
                match = re.match(r"(\d+(?:\.\d+)?)\s*(B|KB|MB|GB)", max_size.upper())
                max_bytes = 10 * 1024 * 1024  # 默认 10MB
                
                if match:
                    size = float(match.group(1))
                    unit = match.group(2)
                    max_bytes = int(size * size_units[unit])
                
                file_handler = RotatingFileHandler(
                    log_path,
                    maxBytes=max_bytes,
                    backupCount=log_config["rotation"].get("backup_count", 5)
                )
            else:
                file_handler = logging.FileHandler(log_path)
            
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def _get_history_file(self) -> Path:
        """获取历史记录文件路径"""
        log_file = self.config.get("security", {}).get("log_file")
        
        if log_file:
            return Path(log_file)
        else:
            return Path.home() / ".openclaw" / "exec_history.json"
    
    def _get_cache_dir(self) -> Path:
        """获取缓存目录"""
        if not self.cache_enabled:
            return None
        
        cache_dir = self.config.get("cache", {}).get("dir")
        if cache_dir:
            cache_path = Path(os.path.expanduser(cache_dir))
        else:
            cache_path = Path.home() / ".openclaw" / "exec_cache"
        
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path
    
    def _load_history(self) -> List[CommandRecord]:
        """加载命令历史"""
        if not self.history_file.exists():
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            history = []
            for record_data in data.get("records", []):
                record = CommandRecord(**record_data)
                history.append(record)
            
            return history
        except Exception as e:
            self.logger.error(f"Failed to load history: {e}")
            return []
    
    def _save_history(self):
        """保存命令历史"""
        try:
            data = {
                "records": [asdict(record) for record in self.command_history],
                "updated_at": datetime.now().isoformat()
            }
            
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save history: {e}")
    
    def _get_allowed_commands(self) -> List[str]:
        """获取当前权限级别允许的命令"""
        if self.permission_level == "admin":
            # 包含所有命令
            all_commands = []
            for level in ["readonly", "readwrite", "admin"]:
                all_commands.extend(self.commands.get(level, []))
            return all_commands
        elif self.permission_level == "readwrite":
            # 包含 readonly 和 readwrite
            all_commands = []
            for level in ["readonly", "readwrite"]:
                all_commands.extend(self.commands.get(level, []))
            return all_commands
        else:
            # 只包含 readonly
            return self.commands.get("readonly", [])
    
    def _check_permission(self, command: str) -> bool:
        """检查命令是否在白名单中"""
        allowed_commands = self._get_allowed_commands()
        return command in allowed_commands
    
    def _check_path_access(self, path: str) -> bool:
        """检查路径是否允许访问"""
        # 展开路径
        path = os.path.expanduser(path)
        path = os.path.abspath(path)
        
        # 检查禁止路径
        forbidden_paths = self.config.get("security", {}).get("forbidden_paths", [])
        
        for forbidden in forbidden_paths:
            forbidden = os.path.expanduser(forbidden)
            if path.startswith(forbidden):
                return False
        
        # 检查允许路径
        allowed_paths = self.config.get("security", {}).get("allowed_paths", [])
        
        if not allowed_paths:  # 如果允许列表为空，则不限制
            return True
        
        for allowed in allowed_paths:
            allowed = os.path.expanduser(allowed)
            if path.startswith(allowed):
                return True
        
        return False
    
    def _check_dangerous_command(self, command_line: str) -> Tuple[bool, Optional[str]]:
        """检查是否为危险命令"""
        dangerous_patterns = self.config.get("security", {}).get("dangerous_patterns", [])
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command_line):
                return False, f"Dangerous pattern detected: {pattern}"
        
        return True, None
    
    def _requires_confirmation(self, command_line: str) -> bool:
        """检查是否需要确认"""
        privileged_commands = self.config.get("security", {}).get("privileged_commands", [])
        
        for privileged in privileged_commands:
            if re.search(privileged, command_line):
                return True
        
        return False
    
    def _validate_command(self, command: str, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证命令"""
        # 检查命令是否在白名单中
        if not self._check_permission(command):
            return False, f"Command '{command}' is not allowed for permission level '{self.permission_level}'"
        
        # 获取命令模板
        template = self.templates.get(command)
        
        if not template:
            return False, f"Command template not found: {command}"
        
        # 检查是否需要确认
        if template.get("confirm", False):
            return False, "Command requires user confirmation"
        
        # 检查参数
        expected_params = template.get("params", {})
        
        for param_name, param_config in expected_params.items():
            if param_config.get("required", False) and param_name not in params:
                return False, f"Required parameter '{param_name}' is missing"
        
        # 检查路径参数
        if template.get("validate_path", False):
            path_param = params.get("path")
            if path_param and not self._check_path_access(path_param):
                return False, f"Access to path '{path_param}' is not allowed"
        
        if template.get("validate_paths", False):
            for param_name in ["source", "dest"]:
                path_param = params.get(param_name)
                if path_param and not self._check_path_access(path_param):
                    return False, f"Access to path '{path_param}' is not allowed"
        
        # 验证脚本文件
        if template.get("validate_script", False):
            script_path = params.get("script")
            if script_path:
                if not self._check_path_access(script_path):
                    return False, f"Access to script '{script_path}' is not allowed"
                
                if not os.path.isfile(script_path):
                    return False, f"Script file not found: {script_path}"
                
                # 检查脚本扩展名
                if not script_path.endswith(('.sh', '.py', '.bash', '.zsh')):
                    return False, f"Invalid script file type: {script_path}"
        
        return True, None
    
    def _build_command(self, command: str, params: Dict[str, Any]) -> str:
        """构建完整命令"""
        template = self.templates.get(command)
        
        if not template:
            raise ValueError(f"Command template not found: {command}")
        
        command_template = template.get("command")
        
        if not command_template:
            raise ValueError(f"Command template missing 'command' field")
        
        # 替换参数
        try:
            # 处理特殊参数（如数组）
            formatted_params = {}
            
            for key, value in params.items():
                if isinstance(value, list):
                    # 数组参数转换为字符串
                    formatted_params[key] = " ".join(map(str, value))
                else:
                    formatted_params[key] = str(value)
            
            command_line = command_template.format(**formatted_params)
            return command_line
        
        except KeyError as e:
            raise ValueError(f"Missing parameter: {e}")
    
    def _execute_command(self, command_line: str, timeout: int = None) -> ExecutionResult:
        """执行命令"""
        start_time = time.time()
        
        if timeout is None:
            timeout = self.config.get("security", {}).get("command_timeout", 60)
        
        max_output_size = self.config.get("security", {}).get("max_output_size", "1MB")
        
        # 转换大小
        size_units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
        import re
        match = re.match(r"(\d+(?:\.\d+)?)\s*(B|KB|MB|GB)", max_output_size.upper())
        max_bytes = 1024 * 1024  # 默认 1MB
        
        if match:
            size = float(match.group(1))
            unit = match.group(2)
            max_bytes = int(size * size_units[unit])
        
        try:
            self.logger.info(f"Executing command: {command_line}")
            
            # 使用 shlex 分割命令
            args = shlex.split(command_line)
            
            # 执行命令
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # 读取输出（限制大小）
            stdout_lines = []
            stderr_lines = []
            
            def read_output(pipe, lines_list):
                for line in iter(pipe.readline, ''):
                    lines_list.append(line)
                    if len(''.join(lines_list)) > max_bytes:
                        lines_list.append("... (output truncated)")
                        break
            
            import threading
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout_lines))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr_lines))
            
            stdout_thread.start()
            stderr_thread.start()
            
            # 等待进程完成或超时
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                exit_code = -1
                stderr_lines.append(f"Command timed out after {timeout} seconds")
            
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            
            duration = int((time.time() - start_time) * 1000)
            
            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)
            
            # 检查退出码
            success = exit_code == 0
            
            if exit_code != 0 and not stderr:
                stderr = f"Command failed with exit code {exit_code}"
            
            result = ExecutionResult(
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration,
                command=command_line
            )
            
            self.logger.info(f"Command completed in {duration}ms, exit code: {exit_code}")
            
            return result
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            
            result = ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration,
                command=command_line,
                error_message=f"Failed to execute command: {e}"
            )
            
            self.logger.error(f"Command execution failed: {e}")
            
            return result
    
    def execute(self, command: str, params: Dict[str, Any] = None, confirmed: bool = False) -> ExecutionResult:
        """
        执行命令
        
        Args:
            command: 命令名称（对应 templates 中的键）
            params: 命令参数
            confirmed: 是否已确认（用于特权命令）
        """
        if params is None:
            params = {}
        
        # 验证命令
        is_valid, error_msg = self._validate_command(command, params)
        
        if not is_valid:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                duration_ms=0,
                command=command,
                error_message=error_msg
            )
        
        # 构建完整命令
        try:
            command_line = self._build_command(command, params)
        except Exception as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
                command=command,
                error_message=f"Failed to build command: {e}"
            )
        
        # 检查危险命令
        is_safe, danger_reason = self._check_dangerous_command(command_line)
        
        if not is_safe:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=danger_reason,
                duration_ms=0,
                command=command_line,
                error_message=f"Dangerous command detected: {danger_reason}"
            )
        
        # 检查是否需要确认
        requires_confirm = self._requires_confirmation(command_line)
        
        if requires_confirm and not confirmed:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Command requires user confirmation",
                duration_ms=0,
                command=command_line,
                error_message="Command requires user confirmation"
            )
        
        # 执行命令
        result = self._execute_command(command_line)
        
        # 记录执行历史
        record = CommandRecord(
            id=f"{int(time.time())}_{hashlib.md5(command_line.encode()).hexdigest()[:8]}",
            timestamp=datetime.now().isoformat(),
            command=command,
            params=params,
            user=os.getenv("USER", "unknown"),
            permission_level=self.permission_level,
            status="success" if result.success else "failed",
            output=result.stdout if result.success else result.stderr,
            error=result.error_message,
            duration_ms=result.duration_ms,
            confirm_required=requires_confirm,
            confirmed=confirmed
        )
        
        self.command_history.append(record)
        self._save_history()
        
        return result
    
    def list_commands(self) -> List[Dict[str, Any]]:
        """列出可用命令"""
        allowed_commands = self._get_allowed_commands()
        
        commands = []
        
        for cmd in allowed_commands:
            template = self.templates.get(cmd)
            if template:
                commands.append({
                    "name": cmd,
                    "description": template.get("description", ""),
                    "permission": template.get("permission", "unknown")
                })
        
        return commands
    
    def get_command_info(self, command: str) -> Optional[Dict[str, Any]]:
        """获取命令详情"""
        template = self.templates.get(command)
        
        if not template:
            return None
        
        info = {
            "name": command,
            "description": template.get("description", ""),
            "permission": template.get("permission", "unknown"),
            "requires_confirmation": template.get("confirm", False),
            "parameters": template.get("params", {}),
            "command_template": template.get("command")
        }
        
        return info
    
    def get_history(self, limit: int = 100) -> List[CommandRecord]:
        """获取执行历史"""
        return self.command_history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.command_history)
        successful = len([r for r in self.command_history if r.status == "success"])
        failed = len([r for r in self.command_history if r.status == "failed"])
        denied = len([r for r in self.command_history if r.status == "denied"])
        
        # 按命令统计
        command_stats = {}
        for record in self.command_history:
            command_stats[record.command] = command_stats.get(record.command, 0) + 1
        
        return {
            "total_commands": total,
            "successful": successful,
            "failed": failed,
            "denied": denied,
            "success_rate": successful / total if total > 0 else 0,
            "by_command": command_stats
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Local Exec CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 列出命令
    list_parser = subparsers.add_parser("list", help="列出可用命令")
    
    # 命令详情
    info_parser = subparsers.add_parser("info", help="查看命令详情")
    info_parser.add_argument("--command", required=True, help="命令名称")
    
    # 执行命令
    exec_parser = subparsers.add_parser("execute", help="执行命令")
    exec_parser.add_argument("--command", required=True, help="命令名称")
    exec_parser.add_argument("--params", type=json.loads, default={}, help="参数（JSON）")
    exec_parser.add_argument("--confirmed", action="store_true", help="已确认执行")
    
    # 历史记录
    history_parser = subparsers.add_parser("history", help="查看执行历史")
    history_parser.add_argument("--limit", type=int, default=20, help="显示最近 N 条记录")
    
    # 统计
    stats_parser = subparsers.add_parser("stats", help="查看统计信息")
    
    # 测试
    test_parser = subparsers.add_parser("test", help="测试命令")
    test_parser.add_argument("--command", required=True, help="命令名称")
    test_parser.add_argument("--params", type=json.loads, default={}, help="参数（JSON）")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    executor = CommandExecutor()
    
    if args.command == "list":
        commands = executor.list_commands()
        
        if not commands:
            print("No commands available")
        else:
            print(f"{'Command':<20} {'Permission':<12} {'Description':<40}")
            print("-" * 75)
            
            for cmd in commands:
                print(f"{cmd['name']:<20} {cmd['permission']:<12} {cmd['description']:<40}")
    
    elif args.command == "info":
        info = executor.get_command_info(args.command)
        
        if not info:
            print(f"Command not found: {args.command}")
            sys.exit(1)
        
        print(f"Command: {info['name']}")
        print(f"Description: {info['description']}")
        print(f"Permission: {info['permission']}")
        print(f"Requires confirmation: {info['requires_confirmation']}")
        
        if info['parameters']:
            print(f"\nParameters:")
            for param_name, param_config in info['parameters'].items():
                required = param_config.get('required', False)
                default = param_config.get('default', 'None')
                print(f"  {param_name}: required={required}, default={default}")
        
        print(f"\nCommand template: {info['command_template']}")
    
    elif args.command == "execute":
        print(f"Executing command: {args.command}")
        print(f"Params: {json.dumps(args.params, indent=2)}")
        
        if args.confirmed:
            print("Confirmed by user")
        
        result = executor.execute(args.command, args.params, confirmed=args.confirmed)
        
        print(f"\nExit code: {result.exit_code}")
        print(f"Duration: {result.duration_ms}ms")
        
        if result.stdout:
            print(f"\nOutput:\n{result.stdout}")
        
        if result.stderr:
            print(f"\nError:\n{result.stderr}")
        
        if not result.success:
            sys.exit(result.exit_code)
    
    elif args.command == "history":
        history = executor.get_history(limit=args.limit)
        
        if not history:
            print("No execution history")
        else:
            print(f"Recent execution history (limit: {args.limit}):")
            print(f"{'ID':<20} {'Command':<15} {'Status':<8} {'Duration':<10} {'Date':<20}")
            print("-" * 85)
            
            for record in history:
                date = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
                duration = f"{record.duration_ms}ms" if record.duration_ms else "N/A"
                print(f"{record.id:<20} {record.command:<15} {record.status:<8} {duration:<10} {date:<20}")
    
    elif args.command == "stats":
        stats = executor.get_stats()
        
        print("Command Execution Statistics:")
        print(f"-" * 40)
        print(f"Total commands: {stats['total_commands']}")
        print(f"Successful: {stats['successful']}")
        print(f"Failed: {stats['failed']}")
        print(f"Denied: {stats['denied']}")
        print(f"Success rate: {stats['success_rate']:.1%}")
        
        if stats['by_command']:
            print(f"\nBy command:")
            for command, count in sorted(stats['by_command'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {command}: {count}")
    
    elif args.command == "test":
        print(f"Testing command: {args.command}")
        print(f"Params: {json.dumps(args.params, indent=2)}")
        
        # 只验证，不执行
        is_valid, error_msg = CommandExecutor()._validate_command(args.command, args.params)
        
        if is_valid:
            print("✓ Command validation passed")
            
            # 构建命令查看
            try:
                command_line = CommandExecutor()._build_command(args.command, args.params)
                print(f"Command would be: {command_line}")
            except Exception as e:
                print(f"Failed to build command: {e}")
        else:
            print(f"✗ Command validation failed: {error_msg}")
            sys.exit(1)


if __name__ == "__main__":
    main()
