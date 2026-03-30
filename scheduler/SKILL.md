---
name: scheduler
description: 定时任务执行器，支持 cron 表达式调度，可定时触发技能执行、发帖、回复等操作，支持技能间联动和任务状态持久化
metadata:
  {
    "openclaw":
      {
        "requires":
          {
            "bins": ["python3"],
            "env": [],
            "config": [],
          },
        "always": false,
        "emoji": "⏰",
        "homepage": "https://github.com/openclaw-skills/scheduler",
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

# Scheduler

定时任务执行器，为 OpenClaw 提供强大的定时调度能力，支持标准 cron 表达式、任务持久化和技能联动。

## 功能特性

### ⏰ 定时调度
- **Cron 表达式**：支持标准 cron 语法（分 时 日 月 周）
- **灵活调度**：支持每分钟、每小时、每天、每周、每月等周期
- **精确控制**：可指定具体时间点执行任务
- **时区支持**：支持多时区配置

### 🔄 技能联动
- **调用其他技能**：定时触发任意 OpenClaw 技能
- **参数传递**：支持向被调用技能传递参数
- **链式任务**：一个任务的输出可作为下一个任务的输入
- **条件执行**：基于条件判断是否执行任务

### 💾 状态持久化
- **任务存储**：使用 JSON 文件存储任务配置
- **执行记录**：记录每次任务执行结果和日志
- **失败重试**：任务失败后可配置自动重试
- **执行历史**：支持查询历史执行记录

### 📊 监控管理
- **任务列表**：查看所有定时任务状态
- **启停控制**：动态启用/禁用任务
- **手动触发**：支持手动立即执行任务
- **日志查看**：查看任务执行详细日志

## 使用方法

### 添加定时任务

通过自然语言添加任务：

```
使用 scheduler 添加一个定时任务：
- 名称：每日早报
-  cron：0 9 * * *（每天早上 9 点）
- 动作：调用 llm-gateway 生成今日新闻摘要
- 参数：prompt="生成今日 AI 领域新闻摘要"
```

### 定时发帖

```
用 scheduler 创建一个任务：
- 名称：定时发帖
- cron：0 10,14,18 * * *
- 动作：执行发帖脚本
- 参数：content="定时发布的内容"
```

### 定时备份

```
添加 scheduler 任务：
- 名称：自动备份
- cron：0 2 * * *（每天凌晨 2 点）
- 动作：调用 auto-backup 技能
```

### 技能联动

```
创建链式任务：
1. 第一步：生成内容（调用 llm-gateway）
2. 第二步：发布内容（调用发布技能）
3. 第三步：通知用户（调用通知技能）
```

## 配置说明

在 `~/.openclaw/openclaw.json` 中配置：

```json
{
  "skills": {
    "entries": {
      "scheduler": {
        "enabled": true,
        "config": {
          "tasks_file": "~/.openclaw/scheduler_tasks.json",
          "log_file": "~/.openclaw/scheduler.log",
          "max_concurrent_tasks": 5,
          "default_timezone": "Asia/Shanghai",
          "retry_on_failure": true,
          "max_retries": 3
        }
      }
    }
  }
}
```

## 任务定义格式

任务存储在 JSON 文件中，格式如下：

```json
{
  "tasks": [
    {
      "id": "daily-news",
      "name": "每日新闻摘要",
      "enabled": true,
      "cron": "0 9 * * *",
      "timezone": "Asia/Shanghai",
      "action": {
        "skill": "llm-unified-gateway",
        "method": "generate",
        "params": {
          "prompt": "生成今日 AI 领域新闻摘要，包含重要进展和应用案例"
        }
      },
      "on_success": {
        "skill": "notification",
        "params": {
          "message": "新闻摘要已生成"
        }
      },
      "on_failure": {
        "retry": true,
        "max_retries": 3,
        "notify": true
      }
    }
  ]
}
```

## 任务字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 任务唯一标识 |
| name | string | 任务名称 |
| enabled | boolean | 是否启用 |
| cron | string | Cron 表达式（分 时 日 月 周） |
| timezone | string | 时区（如 Asia/Shanghai） |
| action | object | 任务执行动作 |
| action.skill | string | 要调用的技能名称 |
| action.method | string | 要调用的方法 |
| action.params | object | 参数 |
| on_success | object | 成功后的操作（可选） |
| on_failure | object | 失败后的操作（可选） |

## Cron 表达式语法

```
┌───────────── 分钟 (0-59)
│ ┌───────────── 小时 (0-23)
│ │ ┌───────────── 日 (1-31)
│ │ │ ┌───────────── 月 (1-12)
│ │ │ │ ┌───────────── 周 (0-7) (0 和 7 都代表周日)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

**常用示例**：
- `* * * * *` - 每分钟
- `0 * * * *` - 每小时整点
- `0 9 * * *` - 每天 9:00
- `0 9 * * 1` - 每周一 9:00
- `0 9 1 * *` - 每月 1 号 9:00

## CLI 命令

### 添加任务

```bash
python scheduler.py add --id daily-news --cron "0 9 * * *" --skill llm-gateway --params '{"prompt": "新闻摘要"}'
```

### 列出任务

```bash
python scheduler.py list
```

### 启用/禁用任务

```bash
python scheduler.py enable --id daily-news
python scheduler.py disable --id daily-news
```

### 手动执行任务

```bash
python scheduler.py run --id daily-news
```

### 查看日志

```bash
python scheduler.py logs --id daily-news --lines 50
```

### 启动调度器

```bash
python scheduler.py start
```

## 依赖要求

- Python 3.8+
- croniter
- pyyaml
- apscheduler

## 日志文件

调度器会记录详细的执行日志：

```
2026-03-31 09:00:00 - INFO - 任务 daily-news 开始执行
2026-03-31 09:00:02 - INFO - 调用技能 llm-gateway
2026-03-31 09:00:05 - INFO - 执行成功，耗时 5.2 秒
2026-03-31 09:00:05 - INFO - 触发 on_success: notification
```

## 注意事项

- 任务 ID 必须唯一
- Cron 表达式使用标准语法
- 确保被调用的技能已启用
- 定期检查日志文件大小
- 重要任务建议配置失败通知

## 许可证

MIT License
