#!/usr/bin/env python3
"""
Auto Backup
自动备份助手
备份 OpenClaw 的记忆文件、对话历史和配置文件到桌面
"""

import os
import sys
import json
import yaml
import tarfile
import hashlib
import logging
import argparse
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import time
import fnmatch


@dataclass
class BackupRecord:
    """备份记录"""
    id: str
    timestamp: str
    label: str
    files: List[str]
    size: int
    size_human: str
    checksum: str
    checksum_algorithm: str
    archive_path: str
    status: str  # success, failed, running
    error: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class SourceConfig:
    """备份源配置"""
    path: str
    label: str
    enabled: bool
    patterns: List[str]
    exclude: List[str]


class BackupManager:
    """备份管理器"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "config.yaml")
        self.config = self._load_config()
        self.logger = self._setup_logging()
        
        # 备份根目录
        self.backup_dir = Path(os.path.expanduser(self.config.get("backup", {}).get("dir", "~/Desktop/OpenClaw_Backups")))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 索引文件
        self.index_file = self.backup_dir / self.config.get("index", {}).get("file", "backup_index.json")
        
        # 加载索引
        self.backups = self._load_index()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 展开路径
        if 'backup' in config and 'dir' in config['backup']:
            config['backup']['dir'] = os.path.expanduser(config['backup']['dir'])
        
        # 处理 source 路径
        if 'sources' in config:
            for source in config['sources']:
                source['path'] = os.path.expanduser(source['path'])
        
        return config
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get("logging", {})
        
        logger = logging.getLogger("backup")
        logger.setLevel(getattr(logging, log_config.get("level", "INFO").upper()))
        
        # 日志文件
        log_file = log_config.get("file")
        if log_file:
            log_path = self.backup_dir / log_file
            handler = logging.FileHandler(log_path)
        else:
            handler = logging.StreamHandler()
        
        formatter = logging.Formatter(log_config.get("format", "%(asctime)s - %(levelname)s - %(message)s"))
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def _load_index(self) -> Dict[str, BackupRecord]:
        """加载备份索引"""
        if not self.index_file.exists():
            return {}
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            backups = {}
            for backup_data in data.get("backups", []):
                backup = BackupRecord(**backup_data)
                backups[backup.id] = backup
            
            return backups
        except Exception as e:
            self.logger.error(f"Failed to load index: {e}")
            return {}
    
    def _save_index(self):
        """保存备份索引"""
        try:
            data = {
                "backups": [asdict(backup) for backup in self.backups.values()],
                "updated_at": datetime.now().isoformat()
            }
            
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save index: {e}")
    
    def _should_include_file(self, file_path: Path, patterns: List[str], exclude_patterns: List[str]) -> bool:
        """判断文件是否应该包含"""
        # 检查排除模式
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(str(file_path), pattern):
                return False
        
        # 检查包含模式
        for pattern in patterns:
            if fnmatch.fnmatch(str(file_path), pattern):
                return True
        
        return False
    
    def _get_files_to_backup(self, source: Dict) -> List[Path]:
        """获取要备份的文件列表"""
        source_path = Path(source['path'])
        
        if not source_path.exists():
            self.logger.warning(f"Source path does not exist: {source_path}")
            return []
        
        patterns = source.get('patterns', ['**/*'])
        exclude_patterns = source.get('exclude', [])
        
        # 添加全局排除规则
        global_exclude = self.config.get('exclude', {}).get('patterns', [])
        exclude_patterns.extend(global_exclude)
        
        files = []
        
        if source_path.is_file():
            # 如果是文件，直接检查是否匹配
            if self._should_include_file(source_path, patterns, exclude_patterns):
                files.append(source_path)
        else:
            # 如果是目录，递归遍历
            for pattern in patterns:
                for file_path in source_path.glob(pattern):
                    if file_path.is_file():
                        if self._should_include_file(file_path, [pattern], exclude_patterns):
                            files.append(file_path)
        
        return files
    
    def _human_readable_size(self, size: int) -> str:
        """转换文件大小为人类可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def _calculate_checksum(self, file_path: Path, algorithm: str = "sha256") -> str:
        """计算文件校验和"""
        hash_func = getattr(hashlib, algorithm.lower())()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        
        return f"{algorithm}:{hash_func.hexdigest()}"
    
    def _create_backup_archive(self, files: List[Path], label: str, timestamp: str) -> Path:
        """创建备份归档"""
        # 备份文件名
        archive_name = f"OpenClaw_Backup_{label}_{timestamp}.tar"
        
        # 根据压缩算法确定扩展名
        compression = self.config.get("compression", {}).get("algorithm", "gzip")
        
        if compression == "gzip":
            archive_name += ".gz"
            mode = "w:gz"
        elif compression == "bzip2":
            archive_name += ".bz2"
            mode = "w:bz2"
        elif compression == "xz":
            archive_name += ".xz"
            mode = "w:xz"
        else:
            mode = "w"
        
        archive_path = self.backup_dir / archive_name
        
        # 创建归档
        with tarfile.open(archive_path, mode) as tar:
            for file_path in files:
                try:
                    # 使用相对路径作为归档内的路径
                    relative_path = file_path.relative_to(Path.home())
                    tar.add(file_path, arcname=str(relative_path))
                    self.logger.debug(f"Added to archive: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to add {file_path} to archive: {e}")
        
        return archive_path
    
    def backup_source(self, source: SourceConfig, verify: bool = True) -> Optional[BackupRecord]:
        """备份单个源"""
        if not source.enabled:
            self.logger.info(f"Source disabled, skipping: {source.label}")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.logger.info(f"Starting backup: {source.label}")
        
        start_time = time.time()
        
        try:
            # 获取要备份的文件
            files = self._get_files_to_backup(asdict(source))
            
            if not files:
                self.logger.warning(f"No files to backup for: {source.label}")
                return None
            
            self.logger.info(f"Found {len(files)} files to backup")
            
            # 创建归档
            archive_path = self._create_backup_archive(files, source.label, timestamp)
            
            # 计算校验和
            checksum = self._calculate_checksum(archive_path) if verify else ""
            
            duration = int((time.time() - start_time) * 1000)
            
            # 创建备份记录
            backup = BackupRecord(
                id=f"{timestamp}_{source.label}",
                timestamp=datetime.now().isoformat(),
                label=source.label,
                files=[str(f.relative_to(Path.home())) for f in files],
                size=archive_path.stat().st_size,
                size_human=self._human_readable_size(archive_path.stat().st_size),
                checksum=checksum,
                checksum_algorithm="sha256",
                archive_path=str(archive_path),
                status="success",
                duration_ms=duration
            )
            
            # 保存到索引
            self.backups[backup.id] = backup
            self._save_index()
            
            self.logger.info(
                f"Backup completed: {source.label} "
                f"({backup.size_human}, {duration}ms)"
            )
            
            return backup
            
        except Exception as e:
            self.logger.error(f"Backup failed for {source.label}: {e}")
            
            backup = BackupRecord(
                id=f"{timestamp}_{source.label}",
                timestamp=datetime.now().isoformat(),
                label=source.label,
                files=[],
                size=0,
                size_human="0 B",
                checksum="",
                checksum_algorithm="sha256",
                archive_path="",
                status="failed",
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000)
            )
            
            self.backups[backup.id] = backup
            self._save_index()
            
            return backup
    
    def backup_all(self, verify: bool = True) -> List[BackupRecord]:
        """备份所有源"""
        sources = self.config.get("sources", [])
        
        if not sources:
            self.logger.warning("No backup sources configured")
            return []
        
        backups = []
        
        for source_config in sources:
            source = SourceConfig(**source_config)
            backup = self.backup_source(source, verify)
            
            if backup:
                backups.append(backup)
            
            # 短暂延迟，避免 IO 过载
            time.sleep(0.5)
        
        # 清理旧备份
        if self.config.get("retention", {}).get("auto_cleanup", False):
            self.cleanup_old_backups()
        
        return backups
    
    def list_backups(self) -> List[BackupRecord]:
        """列出所有备份"""
        return sorted(
            self.backups.values(),
            key=lambda x: x.timestamp,
            reverse=True
        )
    
    def get_backup(self, backup_id: str) -> Optional[BackupRecord]:
        """获取指定备份"""
        return self.backups.get(backup_id)
    
    def verify_backup(self, backup_id: str) -> bool:
        """验证备份完整性"""
        backup = self.backups.get(backup_id)
        
        if not backup:
            self.logger.error(f"Backup not found: {backup_id}")
            return False
        
        if backup.status != "success":
            self.logger.error(f"Backup failed, cannot verify: {backup_id}")
            return False
        
        if not backup.checksum:
            self.logger.warning(f"No checksum for backup: {backup_id}")
            return False
        
        try:
            archive_path = Path(backup.archive_path)
            
            if not archive_path.exists():
                self.logger.error(f"Archive file not found: {archive_path}")
                return False
            
            # 重新计算校验和
            current_checksum = self._calculate_checksum(archive_path, backup.checksum_algorithm)
            
            if current_checksum == backup.checksum:
                self.logger.info(f"Backup verification passed: {backup_id}")
                return True
            else:
                self.logger.error(f"Backup verification failed: {backup_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to verify backup {backup_id}: {e}")
            return False
    
    def restore_backup(self, backup_id: str, target_dir: Optional[str] = None) -> bool:
        """恢复备份"""
        backup = self.backups.get(backup_id)
        
        if not backup:
            self.logger.error(f"Backup not found: {backup_id}")
            return False
        
        if backup.status != "success":
            self.logger.error(f"Backup failed, cannot restore: {backup_id}")
            return False
        
        # 确定目标目录
        if target_dir:
            restore_dir = Path(target_dir)
        else:
            # 默认恢复到临时目录
            restore_dir = self.backup_dir / "restores" / backup_id
        
        restore_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Restoring backup {backup_id} to {restore_dir}")
        
        try:
            archive_path = Path(backup.archive_path)
            
            if not archive_path.exists():
                self.logger.error(f"Archive file not found: {archive_path}")
                return False
            
            # 解压归档
            with tarfile.open(archive_path, 'r') as tar:
                tar.extractall(path=restore_dir)
            
            self.logger.info(f"Backup restored successfully to {restore_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore backup {backup_id}: {e}")
            return False
    
    def cleanup_old_backups(self) -> int:
        """清理旧备份"""
        retention_days = self.config.get("retention", {}).get("days", 30)
        max_count = self.config.get("retention", {}).get("max_count", 100)
        max_total_size = self.config.get("retention", {}).get("max_total_size", "5GB")
        
        # 解析最大大小
        size_units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        max_size_bytes = 0
        
        if isinstance(max_total_size, str):
            import re
            match = re.match(r"(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)", max_total_size.upper())
            if match:
                size = float(match.group(1))
                unit = match.group(2)
                max_size_bytes = int(size * size_units[unit])
        else:
            max_size_bytes = int(max_total_size)
        
        cutoff_time = time.time() - (retention_days * 24 * 3600)
        
        cleaned = 0
        total_size = 0
        
        # 按时间排序（从最旧到最新）
        sorted_backups = sorted(
            self.backups.values(),
            key=lambda x: x.timestamp
        )
        
        for backup in sorted_backups:
            # 跳过正在运行的备份
            if backup.status == "running":
                continue
            
            backup_time = datetime.fromisoformat(backup.timestamp.replace("Z", "+00:00")).timestamp()
            
            should_delete = False
            reason = ""
            
            # 检查保留天数
            if backup_time < cutoff_time:
                should_delete = True
                reason = f"older than {retention_days} days"
            
            # 检查总数量
            if len(self.backups) - cleaned > max_count:
                should_delete = True
                reason = f"exceeds max count ({max_count})"
            
            # 检查总大小
            if total_size + backup.size > max_size_bytes:
                should_delete = True
                reason = f"exceeds max size ({max_total_size})"
            
            if should_delete:
                try:
                    archive_path = Path(backup.archive_path)
                    
                    if archive_path.exists():
                        archive_path.unlink()
                    
                    del self.backups[backup.id]
                    cleaned += 1
                    
                    self.logger.info(f"Cleaned up backup {backup.id}: {reason}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to clean up backup {backup.id}: {e}")
            else:
                total_size += backup.size
        
        if cleaned > 0:
            self._save_index()
            self.logger.info(f"Cleaned up {cleaned} old backups")
        
        return cleaned
    
    def get_stats(self) -> Dict[str, Any]:
        """获取备份统计"""
        backups = self.list_backups()
        
        total_size = sum(backup.size for backup in backups)
        successful_backups = [b for b in backups if b.status == "success"]
        failed_backups = [b for b in backups if b.status == "failed"]
        
        stats = {
            "total_backups": len(backups),
            "successful_backups": len(successful_backups),
            "failed_backups": len(failed_backups),
            "total_size": total_size,
            "total_size_human": self._human_readable_size(total_size),
            "avg_size": total_size // len(backups) if backups else 0,
            "avg_size_human": self._human_readable_size(total_size // len(backups)) if backups else "0 B",
        }
        
        if backups:
            stats["oldest_backup"] = backups[-1].timestamp
            stats["newest_backup"] = backups[0].timestamp
        
        # 按标签统计
        stats_by_label = {}
        for backup in backups:
            if backup.status == "success":
                stats_by_label[backup.label] = stats_by_label.get(backup.label, 0) + backup.size
        
        stats["by_label"] = {k: self._human_readable_size(v) for k, v in stats_by_label.items()}
        
        return stats


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Auto Backup CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 备份
    backup_parser = subparsers.add_parser("backup", help="执行备份")
    backup_parser.add_argument("--source", help="指定备份源路径")
    backup_parser.add_argument("--label", help="备份标签")
    backup_parser.add_argument("--no-verify", action="store_true", help="不验证备份完整性")
    
    # 列出备份
    list_parser = subparsers.add_parser("list", help="列出备份")
    list_parser.add_argument("--limit", type=int, default=10, help="显示最近 N 个备份")
    
    # 备份详情
    info_parser = subparsers.add_parser("info", help="查看备份详情")
    info_parser.add_argument("--backup-id", required=True, help="备份 ID")
    
    # 验证备份
    verify_parser = subparsers.add_parser("verify", help="验证备份")
    verify_parser.add_argument("--backup-id", required=True, help="备份 ID")
    
    # 恢复备份
    restore_parser = subparsers.add_parser("restore", help="恢复备份")
    restore_parser.add_argument("--backup-id", required=True, help="备份 ID")
    restore_parser.add_argument("--target", help="恢复目标目录")
    
    # 清理旧备份
    cleanup_parser = subparsers.add_parser("cleanup", help="清理旧备份")
    
    # 统计
    stats_parser = subparsers.add_parser("stats", help="备份统计")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = BackupManager()
    
    if args.command == "backup":
        if args.source and args.label:
            # 备份指定源
            source = {
                "path": args.source,
                "label": args.label,
                "enabled": True,
                "patterns": ["**/*"],
                "exclude": []
            }
            source_config = SourceConfig(**source)
            backup = manager.backup_source(source_config, verify=not args.no_verify)
            
            if backup:
                print(f"Backup completed: {backup.id}")
            else:
                print("Backup failed")
                sys.exit(1)
        else:
            # 备份所有源
            backups = manager.backup_all(verify=not args.no_verify)
            
            if backups:
                print(f"Completed {len(backups)} backups:")
                for backup in backups:
                    print(f"  - {backup.id}: {backup.label} ({backup.size_human})")
            else:
                print("No backups completed")
    
    elif args.command == "list":
        backups = manager.list_backups()
        
        if not backups:
            print("No backups found")
        else:
            print(f"Recent backups (limit: {args.limit}):")
            print(f"{'ID':<25} {'Label':<15} {'Size':<10} {'Status':<8} {'Date':<20}")
            print("-" * 85)
            
            for backup in backups[:args.limit]:
                date = datetime.fromisoformat(backup.timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
                print(f"{backup.id:<25} {backup.label:<15} {backup.size_human:<10} {backup.status:<8} {date:<20}")
    
    elif args.command == "info":
        backup = manager.get_backup(args.backup_id)
        
        if not backup:
            print(f"Backup not found: {args.backup_id}")
            sys.exit(1)
        
        print(f"Backup ID: {backup.id}")
        print(f"Timestamp: {backup.timestamp}")
        print(f"Label: {backup.label}")
        print(f"Status: {backup.status}")
        print(f"Size: {backup.size_human}")
        print(f"Checksum: {backup.checksum}")
        print(f"Archive: {backup.archive_path}")
        
        if backup.duration_ms:
            print(f"Duration: {backup.duration_ms}ms")
        
        if backup.error:
            print(f"Error: {backup.error}")
        
        print(f"\nFiles ({len(backup.files)}):")
        for file in backup.files[:10]:  # 只显示前10个
            print(f"  - {file}")
        
        if len(backup.files) > 10:
            print(f"  ... and {len(backup.files) - 10} more files")
    
    elif args.command == "verify":
        print(f"Verifying backup: {args.backup_id}")
        
        if manager.verify_backup(args.backup_id):
            print("Verification passed")
        else:
            print("Verification failed")
            sys.exit(1)
    
    elif args.command == "restore":
        print(f"Restoring backup: {args.backup_id}")
        
        if manager.restore_backup(args.backup_id, args.target):
            print("Restore completed successfully")
        else:
            print("Restore failed")
            sys.exit(1)
    
    elif args.command == "cleanup":
        print("Cleaning up old backups...")
        cleaned = manager.cleanup_old_backups()
        print(f"Cleaned up {cleaned} old backups")
    
    elif args.command == "stats":
        stats = manager.get_stats()
        
        print("Backup Statistics:")
        print(f"-" * 40)
        print(f"Total backups: {stats['total_backups']}")
        print(f"Successful: {stats['successful_backups']}")
        print(f"Failed: {stats['failed_backups']}")
        print(f"Total size: {stats['total_size_human']}")
        print(f"Average size: {stats['avg_size_human']}")
        
        if 'oldest_backup' in stats:
            print(f"Oldest backup: {stats['oldest_backup']}")
            print(f"Newest backup: {stats['newest_backup']}")
        
        if stats.get('by_label'):
            print(f"\nBy label:")
            for label, size in stats['by_label'].items():
                print(f"  {label}: {size}")


if __name__ == "__main__":
    main()
