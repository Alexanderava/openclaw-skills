#!/usr/bin/env python3
"""
Scheduler
定时任务调度器
支持 cron 表达式，可定时触发技能执行、发帖、回复等操作
"""

import os
import sys
import json
import yaml
import logging
import argparse
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import threading
import time

# 尝试导入 apscheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.jobstores.memory import MemoryJobStore
    APScheduler_AVAILABLE = True
except ImportError:
    APScheduler_AVAILABLE = False
    print("警告: apscheduler 未安装，部分功能将无法使用")
    print("请运行: pip install apscheduler")

try:
    from croniter import croniter
    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False


@dataclass
class Task:
    """任务定义"""
    id: str
    name: str
    enabled: bool
    cron: str
    timezone: str
    action: Dict[str, Any]
    on_success: Optional[Dict[str, Any]] = None
    on_failure: Optional[Dict[str, Any]] = None
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    error_count: int = 0
    created_at: str = None
    updated_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()


@dataclass
class ExecutionRecord:
    """执行记录"""
    task_id: str
    task_name: str
    started_at: str
    completed_at: Optional[str] = None
    status: str = "running"  # running, success, failed
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "config.yaml")
        self.config = self._load_config()
        self.tasks: Dict[str, Task] = {}
        self.scheduler = None
        self.logger = self._setup_logging()
        self._running = False
        self._lock = threading.Lock()
        
        # 初始化存储目录
        self._init_storage()
        
        # 加载任务
        self.load_tasks()
        
        # 初始化调度器
        if APScheduler_AVAILABLE:
            self._init_scheduler()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 展开路径中的 ~
        if 'tasks' in config and 'file' in config['tasks']:
            config['tasks']['file'] = os.path.expanduser(config['tasks']['file'])
        
        if 'logging' in config and 'file' in config['logging']:
            config['logging']['file'] = os.path.expanduser(config['logging']['file'])
        
        if 'execution' in config and 'history_file' in config['execution']:
            config['execution']['history_file'] = os.path.expanduser(config['execution']['history_file'])
        
        return config
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get("logging", {})
        
        logger = logging.getLogger("scheduler")
        logger.setLevel(getattr(logging, log_config.get("level", "INFO").upper()))
        
        # 创建日志目录
        log_file = log_config.get("file")
        if log_file:
            log_dir = os.path.dirname(log_file)
            os.makedirs(log_dir, exist_ok=True)
            
            # 日志轮转
            if self.config.get("execution", {}).get("record_history", False):
                from logging.handlers import RotatingFileHandler
                handler = RotatingFileHandler(
                    log_file,
                    maxBytes=10*1024*1024,  # 10MB
                    backupCount=log_config.get("rotation", {}).get("backup_count", 5)
                )
            else:
                handler = logging.FileHandler(log_file)
        else:
            handler = logging.StreamHandler()
        
        formatter = logging.Formatter(log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def _init_storage(self):
        """初始化存储目录"""
        # 创建任务文件目录
        tasks_file = self.config.get("tasks", {}).get("file")
        if tasks_file:
            tasks_dir = os.path.dirname(tasks_file)
            os.makedirs(tasks_dir, exist_ok=True)
        
        # 创建历史记录目录
        history_file = self.config.get("execution", {}).get("history_file")
        if history_file:
            history_dir = os.path.dirname(history_file)
            os.makedirs(history_dir, exist_ok=True)
    
    def _init_scheduler(self):
        """初始化 APScheduler"""
        if not APScheduler_AVAILABLE:
            self.logger.warning("APScheduler not available, scheduler functionality limited")
            return
        
        jobstores = {
            'default': MemoryJobStore()
        }
        
        timezone = self.config.get("scheduler", {}).get("timezone", "Asia/Shanghai")
        
        self.scheduler = BackgroundScheduler(jobstores=jobstores, timezone=timezone)
        self.scheduler.start()
        self.logger.info("Scheduler started")
        
        # 添加已有任务
        self._schedule_all_tasks()
    
    def load_tasks(self):
        """加载任务"""
        tasks_file = self.config.get("tasks", {}).get("file")
        if not tasks_file or not os.path.exists(tasks_file):
            # 创建默认任务
            default_tasks = self.config.get("tasks", {}).get("default_tasks", [])
            for task_data in default_tasks:
                task = Task(**task_data)
                self.tasks[task.id] = task
            self.logger.info(f"Created {len(default_tasks)} default tasks")
            self.save_tasks()
            return
        
        try:
            with open(tasks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for task_data in data.get("tasks", []):
                task = Task(**task_data)
                self.tasks[task.id] = task
            
            self.logger.info(f"Loaded {len(self.tasks)} tasks from {tasks_file}")
        except Exception as e:
            self.logger.error(f"Failed to load tasks: {e}")
    
    def save_tasks(self):
        """保存任务"""
        tasks_file = self.config.get("tasks", {}).get("file")
        if not tasks_file:
            return
        
        try:
            data = {
                "tasks": [asdict(task) for task in self.tasks.values()],
                "updated_at": datetime.now().isoformat()
            }
            
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Saved {len(self.tasks)} tasks to {tasks_file}")
        except Exception as e:
            self.logger.error(f"Failed to save tasks: {e}")
    
    def add_task(self, task: Task) -> bool:
        """添加任务"""
        if task.id in self.tasks:
            self.logger.error(f"Task {task.id} already exists")
            return False
        
        # 验证 cron 表达式
        if not self._validate_cron(task.cron):
            self.logger.error(f"Invalid cron expression: {task.cron}")
            return False
        
        self.tasks[task.id] = task
        self.save_tasks()
        
        # 调度任务
        if task.enabled and self.scheduler:
            self._schedule_task(task)
        
        self.logger.info(f"Added task: {task.name} ({task.id})")
        return True
    
    def update_task(self, task_id: str, **kwargs) -> bool:
        """更新任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        task.updated_at = datetime.now().isoformat()
        self.save_tasks()
        
        # 重新调度
        if self.scheduler:
            self.scheduler.remove_job(task_id)
            if task.enabled:
                self._schedule_task(task)
        
        self.logger.info(f"Updated task: {task.name} ({task_id})")
        return True
    
    def remove_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        del self.tasks[task_id]
        self.save_tasks()
        
        # 取消调度
        if self.scheduler:
            self.scheduler.remove_job(task_id)
        
        self.logger.info(f"Removed task: {task.name} ({task_id})")
        return True
    
    def enable_task(self, task_id: str) -> bool:
        """启用任务"""
        return self.update_task(task_id, enabled=True)
    
    def disable_task(self, task_id: str) -> bool:
        """禁用任务"""
        return self.update_task(task_id, enabled=False)
    
    def _validate_cron(self, cron_expr: str) -> bool:
        """验证 cron 表达式"""
        if not CRONITER_AVAILABLE:
            # 如果 croniter 不可用，简单验证格式
            parts = cron_expr.split()
            if len(parts) != 5:
                return False
            return True
        
        try:
            croniter(cron_expr)
            return True
        except:
            return False
    
    def _schedule_all_tasks(self):
        """调度所有启用的任务"""
        for task in self.tasks.values():
            if task.enabled:
                self._schedule_task(task)
    
    def _schedule_task(self, task: Task):
        """调度单个任务"""
        if not self.scheduler:
            return
        
        try:
            trigger = CronTrigger.from_crontab(task.cron, timezone=task.timezone)
            
            self.scheduler.add_job(
                func=self._execute_task,
                trigger=trigger,
                id=task.id,
                args=[task.id],
                replace_existing=True,
                misfire_grace_time=self.config.get("scheduler", {}).get("misfire_grace_time", 60)
            )
            
            self.logger.info(f"Scheduled task: {task.name} ({task.id}) - {task.cron}")
        except Exception as e:
            self.logger.error(f"Failed to schedule task {task.id}: {e}")
    
    def _execute_task(self, task_id: str):
        """执行任务"""
        if task_id not in self.tasks:
            self.logger.error(f"Task {task_id} not found")
            return
        
        task = self.tasks[task_id]
        
        with self._lock:
            task.run_count += 1
            task.last_run = datetime.now().isoformat()
            self.save_tasks()
        
        record = ExecutionRecord(
            task_id=task_id,
            task_name=task.name,
            started_at=datetime.now().isoformat()
        )
        
        self.logger.info(f"Task started: {task.name} ({task_id})")
        
        try:
            start_time = time.time()
            
            # 执行任务动作
            result = self._execute_action(task.action)
            
            duration = int((time.time() - start_time) * 1000)
            record.completed_at = datetime.now().isoformat()
            record.status = "success"
            record.result = str(result)
            record.duration_ms = duration
            
            self.logger.info(f"Task completed: {task.name} ({task_id}) - {duration}ms")
            
            # 执行成功后的操作
            if task.on_success:
                self._execute_action(task.on_success)
            
        except Exception as e:
            error_msg = str(e)
            record.completed_at = datetime.now().isoformat()
            record.status = "failed"
            record.error = error_msg
            record.duration_ms = int((time.time() - start_time) * 1000)
            
            task.error_count += 1
            self.save_tasks()
            
            self.logger.error(f"Task failed: {task.name} ({task_id}) - {error_msg}")
            
            # 执行失败后的操作
            if task.on_failure:
                if task.on_failure.get("retry", False):
                    self._handle_retry(task, e)
                if task.on_failure.get("notify", False):
                    self._send_notification(task, error_msg)
        
        # 保存执行记录
        self._save_execution_record(record)
    
    def _execute_action(self, action: Dict[str, Any]) -> Any:
        """执行动作"""
        skill = action.get("skill")
        method = action.get("method", "execute")
        params = action.get("params", {})
        
        if not skill:
            raise ValueError("Action must specify a skill")
        
        # 这里应该调用 OpenClaw 的技能系统
        # 暂时使用子进程模拟
        cmd = ["python3", "-c", f"print('Executing {skill}.{method} with params: {params}')"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            raise Exception(f"Action failed: {result.stderr}")
        
        return result.stdout.strip()
    
    def _handle_retry(self, task: Task, error: Exception):
        """处理重试"""
        retry_config = task.on_failure.get("retry_config", {})
        max_retries = retry_config.get("max_retries", 3)
        
        if task.error_count >= max_retries:
            self.logger.warning(f"Task {task.id} reached max retries")
            return
        
        delay = retry_config.get("initial_delay", 60)
        self.logger.info(f"Will retry task {task.id} after {delay}s")
        
        # 这里应该使用调度器安排重试
        # 暂时简单处理
        # TODO: 实现真正的重试调度
    
    def _send_notification(self, task: Task, error_msg: str):
        """发送通知"""
        self.logger.info(f"Sending notification for failed task {task.id}: {error_msg}")
        # TODO: 实现通知功能（webhook, email 等）
    
    def _save_execution_record(self, record: ExecutionRecord):
        """保存执行记录"""
        if not self.config.get("execution", {}).get("record_history", False):
            return
        
        history_file = self.config.get("execution", {}).get("history_file")
        if not history_file:
            return
        
        try:
            history_file = os.path.expanduser(history_file)
            
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"records": []}
            
            data["records"].append(asdict(record))
            
            # 清理旧记录
            keep_days = self.config.get("execution", {}).get("keep_days", 30)
            cutoff_time = time.time() - (keep_days * 24 * 3600)
            
            data["records"] = [
                r for r in data["records"]
                if datetime.fromisoformat(r["started_at"].replace("Z", "+00:00")).timestamp() > cutoff_time
            ]
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            self.logger.error(f"Failed to save execution record: {e}")
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def list_tasks(self) -> List[Task]:
        """列出所有任务"""
        return list(self.tasks.values())
    
    def start(self):
        """启动调度器"""
        if not self.scheduler:
            self.logger.error("Scheduler not available")
            return
        
        if not self._running:
            self._running = True
            self.logger.info("Scheduler is running...")
            
            try:
                while self._running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
    
    def stop(self):
        """停止调度器"""
        self._running = False
        
        if self.scheduler:
            self.scheduler.shutdown()
        
        self.logger.info("Scheduler stopped")
    
    def run_task(self, task_id: str):
        """手动运行任务"""
        self._execute_task(task_id)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Task Scheduler CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 添加任务
    add_parser = subparsers.add_parser("add", help="添加任务")
    add_parser.add_argument("--id", required=True, help="任务 ID")
    add_parser.add_argument("--name", required=True, help="任务名称")
    add_parser.add_argument("--cron", required=True, help="Cron 表达式")
    add_parser.add_argument("--timezone", default="Asia/Shanghai", help="时区")
    add_parser.add_argument("--skill", required=True, help="技能名称")
    add_parser.add_argument("--method", default="execute", help="方法名称")
    add_parser.add_argument("--params", type=json.loads, default={}, help="参数（JSON）")
    
    # 列出任务
    list_parser = subparsers.add_parser("list", help="列出任务")
    
    # 启用/禁用任务
    enable_parser = subparsers.add_parser("enable", help="启用任务")
    enable_parser.add_argument("--id", required=True, help="任务 ID")
    
    disable_parser = subparsers.add_parser("disable", help="禁用任务")
    disable_parser.add_argument("--id", required=True, help="任务 ID")
    
    # 删除任务
    remove_parser = subparsers.add_parser("remove", help="删除任务")
    remove_parser.add_argument("--id", required=True, help="任务 ID")
    
    # 手动运行任务
    run_parser = subparsers.add_parser("run", help="运行任务")
    run_parser.add_argument("--id", required=True, help="任务 ID")
    
    # 启动调度器
    start_parser = subparsers.add_parser("start", help="启动调度器")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    scheduler = TaskScheduler()
    
    if args.command == "add":
        task = Task(
            id=args.id,
            name=args.name,
            enabled=True,
            cron=args.cron,
            timezone=args.timezone,
            action={
                "skill": args.skill,
                "method": args.method,
                "params": args.params
            }
        )
        
        if scheduler.add_task(task):
            print(f"Task added: {args.id}")
        else:
            print(f"Failed to add task: {args.id}")
            sys.exit(1)
    
    elif args.command == "list":
        tasks = scheduler.list_tasks()
        if not tasks:
            print("No tasks found")
        else:
            print(f"{'ID':<20} {'Name':<20} {'Cron':<15} {'Enabled':<8} {'Runs':<6}")
            print("-" * 80)
            for task in tasks:
                print(f"{task.id:<20} {task.name:<20} {task.cron:<15} {str(task.enabled):<8} {task.run_count:<6}")
    
    elif args.command == "enable":
        if scheduler.enable_task(args.id):
            print(f"Task enabled: {args.id}")
        else:
            print(f"Task not found: {args.id}")
            sys.exit(1)
    
    elif args.command == "disable":
        if scheduler.disable_task(args.id):
            print(f"Task disabled: {args.id}")
        else:
            print(f"Task not found: {args.id}")
            sys.exit(1)
    
    elif args.command == "remove":
        if scheduler.remove_task(args.id):
            print(f"Task removed: {args.id}")
        else:
            print(f"Task not found: {args.id}")
            sys.exit(1)
    
    elif args.command == "run":
        print(f"Running task: {args.id}")
        scheduler.run_task(args.id)
    
    elif args.command == "start":
        print("Starting scheduler... Press Ctrl+C to stop")
        try:
            scheduler.start()
        except KeyboardInterrupt:
            print("\nStopping scheduler...")
            scheduler.stop()


if __name__ == "__main__":
    main()
