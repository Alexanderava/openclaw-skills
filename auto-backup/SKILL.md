---
name: auto-backup
description: 自动备份助手，定期备份 OpenClaw 的记忆文件、对话历史和配置文件到桌面指定目录，支持增量备份和自动清理旧备份
metadata:
  {
    "openclaw":
      {
        "requires":
          {
            "bins": ["python3", "tar", "cp"],
            "env": [],
            "config": [],
          },
        "always": false,
        "emoji": "💾",
        "homepage": "https://github.com/openclaw-skills/auto-backup",
        "install":
          [
            {
              "name": "安装 Python 依赖",
              "cmd": "pip install -r {baseDir}/requirements.txt",
            },
          ],
      },
  }
---

# Auto Backup

自动备份助手，为 OpenClaw 提供安全可靠的数据备份方案，自动备份记忆文件、对话历史和配置文件。

## 功能特性

### 💾 自动备份
- **记忆文件备份**：备份 `.openclaw/memory/` 目录下的所有记忆文件
- **对话历史备份**：备份对话历史和聊天记录
- **配置文件备份**：备份 `openclaw.json` 和其他配置文件
- **技能文件备份**：备份自定义技能和配置

### 📁 智能存储
- **桌面目录**：自动备份到桌面 `OpenClaw_Backups/` 目录
- **时间戳命名**：备份文件按时间戳命名，便于管理
- **增量备份**：支持增量备份，节省存储空间
- **压缩存储**：自动压缩备份文件，减少空间占用

### 🔄 定时备份
- **灵活调度**：支持 cron 表达式配置备份频率
- **多备份策略**：支持每日、每周、每月备份
- **保留策略**：自动清理旧备份， configurable 保留天数
- **备份验证**：备份完成后验证文件完整性

### 📊 备份管理
- **备份列表**：查看所有备份记录
- **备份恢复**：支持从备份恢复数据
- **备份状态**：查看备份成功/失败状态
- **存储统计**：显示备份占用的存储空间

## 使用方法

### 立即备份

```
使用 auto-backup 立即执行备份
```

### 定时备份

与 scheduler 技能配合使用：

```
使用 scheduler 添加定时任务：
- 名称：每日备份
- cron：0 2 * * *（每天凌晨 2 点）
- 动作：调用 auto-backup
```

### 备份指定目录

```
调用 auto-backup 备份指定目录：
- source: ~/.openclaw/skills
- label: 自定义技能备份
```

### 查看备份列表

```
使用 auto-backup 列出所有备份
```

### 恢复备份

```
使用 auto-backup 恢复指定备份：
- backup_id: 20260331_023000
- restore_to: ~/.openclaw/restored/
```

## 配置说明

在 `~/.openclaw/openclaw.json` 中配置：

```json
{
  "skills": {
    "entries": {
      "auto-backup": {
        "enabled": true,
        "config": {
          "backup_dir": "~/Desktop/OpenClaw_Backups",
          "sources": [
            {
              "path": "~/.openclaw/memory",
              "label": "memory_files",
              "patterns": ["**/*.md", "**/*.txt"]
            },
            {
              "path": "~/.openclaw/openclaw.json",
              "label": "config_file",
              "patterns": ["*.json"]
            },
            {
              "path": "~/.openclaw/skills",
              "label": "custom_skills",
              "patterns": ["**/SKILL.md", "**/*.yaml", "**/*.py"]
            }
          ],
          "compression": "gzip",  # none, gzip, bzip2, xz
          "retention_days": 30,
          "max_backup_size": "1GB",
          "verify_after_backup": true,
          "create_index": true
        }
      }
    }
  }
}
```

## 备份源配置

### 记忆文件备份

```yaml
sources:
  - path: ~/.openclaw/memory
    label: memory_files
    patterns:
      - "**/*.md"      # 记忆文件
      - "**/*.txt"     # 文本备份
      - "**/*.json"    # JSON 配置
```

### 对话历史备份

```yaml
sources:
  - path: ~/.openclaw/conversations
    label: conversations
    patterns:
      - "**/*.json"    # 对话历史
      - "**/*.log"     # 日志文件
```

### 技能文件备份

```yaml
sources:
  - path: ~/.openclaw/skills
    label: custom_skills
    patterns:
      - "**/SKILL.md"    # 技能描述
      - "**/*.yaml"      # 配置文件
      - "**/*.py"        # Python 脚本
      - "**/*.json"      # JSON 配置
```

## 备份文件命名

备份文件采用以下命名格式：

```
OpenClaw_Backup_<LABEL>_<TIMESTAMP>.tar.gz
```

示例：
```
OpenClaw_Backup_memory_files_20260331_023000.tar.gz
OpenClaw_Backup_config_file_20260331_023000.tar.gz
OpenClaw_Backup_custom_skills_20260331_023000.tar.gz
```

## 备份索引

启用 `create_index: true` 时，会创建 `backup_index.json`：

```json
{
  "backups": [
    {
      "id": "20260331_023000",
      "timestamp": "2026-03-31T02:30:00",
      "label": "memory_files",
      "files": ["MEMORY.md", "2026-03-31.md"],
      "size": "15KB",
      "checksum": "sha256:abc123...",
      "status": "success"
    }
  ]
}
```

## CLI 命令

### 立即备份

```bash
python backup.py backup
```

### 备份指定目录

```bash
python backup.py backup --source ~/.openclaw/skills --label custom_skills
```

### 列出备份

```bash
python backup.py list
```

### 查看备份详情

```bash
python backup.py info --backup-id 20260331_023000
```

### 验证备份

```bash
python backup.py verify --backup-id 20260331_023000
```

### 恢复备份

```bash
python backup.py restore --backup-id 20260331_023000 --target ~/.openclaw/restore/
```

### 清理旧备份

```bash
python backup.py cleanup
```

## 备份存储统计

查看备份占用空间：

```bash
python backup.py stats
```

输出示例：
```
备份统计：
- 总备份数：15
- 总大小：156MB
- 平均大小：10.4MB
- 最旧备份：2026-03-01
- 最新备份：2026-03-31
```

## 恢复说明

### 完全恢复

```bash
# 恢复所有备份到原始位置
python backup.py restore-all
```

### 选择性恢复

```bash
# 只恢复记忆文件
python backup.py restore --label memory_files --latest
```

### 恢复到指定目录

```bash
# 恢复到临时目录检查
python backup.py restore --backup-id 20260331_023000 --target /tmp/restore/
```

## 依赖要求

- Python 3.8+
- pyyaml
- tarfile
- hashlib
- shutil

## 注意事项

- 备份前确保有足够的磁盘空间
- 建议定期检查备份完整性
- 重要数据建议多重备份
- 恢复前建议先备份当前数据
- 压缩备份需要额外的 CPU 资源

## 许可证

MIT License
