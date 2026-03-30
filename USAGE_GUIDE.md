# OpenClaw 技能套装 - 详细使用指南

本指南详细介绍每个技能的具体使用场景、配置方法和实际用例。

---

## 📚 目录

1. [llm-unified-gateway - 多模型统一调用网关](#1-llm-unified-gateway---多模型统一调用网关)
2. [scheduler - 定时任务执行器](#2-scheduler---定时任务执行器)
3. [auto-backup - 自动备份助手](#3-auto-backup---自动备份助手)
4. [local-exec - 安全命令执行器](#4-local-exec---安全命令执行器)

---

## 1. llm-unified-gateway - 多模型统一调用网关

### 🎯 核心用处

解决多个 AI 模型分散管理的问题，提供统一的调用接口，实现：
- **智能路由**：自动选择最优模型
- **成本优化**：优先使用低成本/免费模型
- **高可用**：模型故障自动切换
- **统一格式**：所有模型返回相同数据结构

### 🔧 配置方法

在 `~/.openclaw/openclaw.json` 中添加：

```json
{
  "skills": {
    "entries": {
      "llm-unified-gateway": {
        "enabled": true,
        "env": {
          "OPENAI_API_KEY": "your-openai-key",
          "GEMINI_API_KEY": "your-gemini-key",
          "MINIMAX_API_KEY": "your-minimax-key",
          "GLM_API_KEY": "your-glm-key"
        },
        "config": {
          "primary_model": "gpt-4",
          "fallback_models": ["gemini-pro", "glm-4"],
          "load_balancing": "round_robin",
          "max_retries": 3,
          "timeout": 30
        }
      }
    }
  }
}
```

### 📝 使用示例

#### 场景 1：日常对话（自动选择最优模型）

```
使用 llm-gateway 生成一段关于 AI 的简介
```

系统会自动选择当前可用的最佳模型（考虑响应速度和成本）。

#### 场景 2：指定模型对比

```
调用 llm-gateway 使用 GPT-4 和 Gemini 分别翻译这段文本，对比质量
- 文本：人工智能正在改变世界
```

同时使用多个模型，对比输出结果。

#### 场景 3：成本敏感任务

```
用 llm-gateway 生成产品描述，优先使用免费模型
- 产品：智能手表
- 特点：健康监测、长续航、防水
```

系统自动优先选择免费或低成本模型。

#### 场景 4：高可靠性要求

```
调用 llm-gateway 分析这段代码的 bug，要求 99.9% 可用性
- 代码：
  ```python
  def divide(a, b):
      return a / b
  ```
```

启用失败重试和自动降级，确保任务完成。

### 📊 返回格式

所有模型统一返回：

```json
{
  "model": "gpt-4",
  "response": "生成的文本内容",
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 150,
    "total_tokens": 250
  },
  "cost": 0.005,
  "latency_ms": 1200,
  "timestamp": "2026-03-31T02:30:00Z"
}
```

---

## 2. scheduler - 定时任务执行器

### 🎯 核心用处

自动化执行重复性任务：
- **定时发帖**：每天在固定时间发布内容
- **自动备份**：定期备份重要数据
- **监控告警**：定时检查系统状态
- **工作流自动化**：多个技能按顺序执行

### 🔧 配置方法

在 `~/.openclaw/openclaw.json` 中添加：

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

### 📝 使用示例

#### 场景 1：每日早报（每天早上 9 点）

```
使用 scheduler 添加一个定时任务：
- 名称：每日早报
- cron：0 9 * * *（每天早上 9 点）
- 动作：调用 llm-gateway 生成今日 AI 新闻摘要
- 参数：
  - prompt：生成今日 AI 领域的重要新闻和进展摘要，包含技术突破、产品发布和行业动态
```

#### 场景 2：定时备份（每天凌晨 2 点）

```
使用 scheduler 创建备份任务：
- 名称：自动备份
- cron：0 2 * * *（每天凌晨 2 点）
- 动作：调用 auto-backup 执行完整备份
```

#### 场景 3：多平台发帖（每天 10 点、14 点、18 点）

```
使用 scheduler 创建定时发帖任务：
- 名称：多平台内容发布
- cron：0 10,14,18 * * *
- 动作链：
  1. 调用 llm-gateway 生成今日话题内容
  2. 调用发布技能发布到各平台
  3. 调用通知技能发送发布报告
```

#### 场景 4：监控告警（每 5 分钟检查一次）

```
使用 scheduler 添加监控任务：
- 名称：磁盘空间监控
- cron：*/5 * * * *（每 5 分钟）
- 动作：调用 local-exec 检查磁盘空间
- 条件：如果使用率 > 80%，调用通知技能发送告警
```

### 📅 Cron 表达式速查

```
* * * * *
│ │ │ │ │
│ │ │ │ └─── 周 (0-7, 0 和 7 都是周日)
│ │ │ └───── 月 (1-12)
│ │ └─────── 日 (1-31)
│ └───────── 时 (0-23)
└─────────── 分 (0-59)
```

**常用示例**：
- `* * * * *` - 每分钟
- `0 * * * *` - 每小时整点
- `0 9 * * *` - 每天 9:00
- `0 9 * * 1` - 每周一 9:00
- `0 9 1 * *` - 每月 1 号 9:00
- `*/30 * * * *` - 每 30 分钟

---

## 3. auto-backup - 自动备份助手

### 🎯 核心用处

保护重要数据，防止意外丢失：
- **记忆备份**：备份 OpenClaw 记忆文件
- **配置备份**：备份所有技能配置
- **对话历史**：备份聊天记录
- **自动清理**：自动删除旧备份，节省空间

### 🔧 配置方法

在 `~/.openclaw/openclaw.json` 中添加：

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
              "patterns": ["**/*.md", "**/*.txt", "**/*.json"]
            },
            {
              "path": "~/.openclaw/openclaw.json",
              "label": "config_file",
              "patterns": ["*.json"]
            },
            {
              "path": "~/.openclaw/skills",
              "label": "custom_skills",
              "patterns": ["**/SKILL.md", "**/*.yaml", "**/*.py", "**/*.json"]
            }
          ],
          "compression": "gzip",
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

### 📝 使用示例

#### 场景 1：立即备份（手动触发）

```
使用 auto-backup 立即执行完整备份
```

立即备份所有配置的记忆文件和配置。

#### 场景 2：查看备份历史

```
使用 auto-backup 列出所有备份
```

显示备份列表：
```
备份列表：
1. OpenClaw_Backup_memory_files_20260331_023000.tar.gz (15KB)
2. OpenClaw_Backup_config_file_20260331_023000.tar.gz (3KB)
3. OpenClaw_Backup_custom_skills_20260331_023000.tar.gz (128KB)
```

#### 场景 3：恢复特定备份

```
使用 auto-backup 恢复指定备份：
- backup_id: 20260331_023000
- restore_to: ~/.openclaw/restored/
```

将指定备份恢复到目标目录。

#### 场景 4：备份统计

```
使用 auto-backup 查看备份统计
```

显示备份占用情况：
```
备份统计：
- 总备份数：15
- 总大小：156MB
- 平均大小：10.4MB
- 最旧备份：2026-03-01
- 最新备份：2026-03-31
```

#### 场景 5：与 scheduler 配合（自动备份）

```
使用 scheduler 添加自动备份任务：
- 名称：每日自动备份
- cron：0 2 * * *（每天凌晨 2 点）
- 动作：调用 auto-backup 执行备份
```

### 📦 备份文件命名规则

```
OpenClaw_Backup_<LABEL>_<TIMESTAMP>.tar.gz

示例：
- OpenClaw_Backup_memory_files_20260331_023000.tar.gz
- OpenClaw_Backup_config_file_20260331_023000.tar.gz
- OpenClaw_Backup_custom_skills_20260331_023000.tar.gz
```

---

## 4. local-exec - 安全命令执行器

### 🎯 核心用处

在受控环境下执行系统命令：
- **系统监控**：查看系统状态、资源使用
- **日志分析**：查看和分析日志文件
- **文件管理**：安全的文件操作
- **服务管理**：启动、停止、重启服务

### 🔧 配置方法

在 `~/.openclaw/openclaw.json` 中添加：

```json
{
  "skills": {
    "entries": {
      "local-exec": {
        "enabled": true,
        "config": {
          "permission_level": "readonly",
          "require_confirmation": true,
          "enable_logging": true,
          "log_file": "~/.openclaw/exec.log",
          "command_timeout": 60,
          "max_output_size": "1MB",
          "allowed_paths": [
            "~/.openclaw",
            "~/Desktop",
            "/tmp"
          ],
          "forbidden_paths": [
            "/etc",
            "/usr/bin",
            "/usr/sbin"
          ]
        }
      }
    }
  }
}
```

### 📝 使用示例

#### 场景 1：查看系统状态

```
使用 local-exec 查看系统信息
```

返回：
```
系统信息：
- OS: Darwin Kernel 22.6.0
- Uptime: 3 days, 12 hours
- CPU: 15% usage
- Memory: 8GB / 16GB (50%)
- Disk: 120GB / 500GB (24%)
```

#### 场景 2：查看日志文件

```
使用 local-exec 查看最新日志：
- 命令：tail-log
- 参数：
  - file: ~/.openclaw/scheduler.log
  - lines: 100
```

显示日志文件最后 100 行。

#### 场景 3：检查磁盘空间

```
使用 local-exec 检查磁盘空间
```

返回：
```
磁盘使用情况：
/     120GB / 500GB  24%  ✅ 正常
/home 45GB  / 200GB  22%  ✅ 正常
```

#### 场景 4：网络连通性测试

```
使用 local-exec 测试网络：
- 命令：test-network
- 参数：
  - host: 8.8.8.8
  - count: 3
  - url: https://api.openai.com
```

测试网络连接和 API 可达性。

#### 场景 5：清理临时文件（需确认）

```
使用 local-exec 清理临时文件：
- 命令：cleanup-temp
- 参数：
  - path: /tmp
- 确认：yes
```

删除指定目录下的临时文件（需要明确确认）。

### 🔐 权限级别说明

#### readonly（只读）- 推荐默认

允许命令：`cat`, `ls`, `pwd`, `df`, `du`, `ps`, `top`, `ping`, `curl`, `tail`, `grep`, `head`, `wc`, `find`, `file`, `stat`, `whoami`, `uname`, `date`, `env`, `which`

#### readwrite（读写）

包含只读命令，外加：`cp`, `mv`, `rm`（限制）, `touch`, `mkdir`, `rmdir`, `echo`, `tee`（限制）, `chmod`（限制）, `chown`（限制）, `ln`, `zip`, `unzip`, `tar`（限制）, `gzip`, `gunzip`

#### admin（管理）

包含读写命令，外加：`sudo`（需要确认）, `systemctl`（限制）, `service`（限制）, `kill`（限制）, `pkill`（限制）, `shutdown`（需要确认）, `reboot`（需要确认）, `mount`（需要确认）, `umount`（需要确认）, `ifconfig`, `iptables`（限制）, `netstat`, `ss`, `lsof`, `strace`（限制）, `vmstat`, `iostat`, `free`, `uptime`, `dmesg`（限制）

---

## 🚀 组合使用场景

### 场景 1：全自动内容创作与发布

```mermaid
scheduler (每天 9:00) → llm-gateway (生成内容) → scheduler (发布到各平台) → auto-backup (备份发布记录)
```

**实现步骤**：
1. Scheduler 定时触发（每天 9:00）
2. 调用 llm-gateway 生成今日内容
3. 调用发布技能发布到各平台
4. 调用 auto-backup 备份发布记录

### 场景 2：智能监控与告警

```mermaid
scheduler (每 5 分钟) → local-exec (检查磁盘) → [如果 > 80%] → llm-gateway (生成告警信息) → [通知用户]
```

**实现步骤**：
1. Scheduler 每 5 分钟检查一次
2. 调用 local-exec 检查磁盘空间
3. 如果超过阈值，调用 llm-gateway 生成告警信息
4. 发送通知给用户

### 场景 3：开发工作流自动化

```mermaid
scheduler (每次提交后) → local-exec (运行测试) → [如果失败] → llm-gateway (分析错误) → auto-backup (备份错误日志)
```

**实现步骤**：
1. Git 提交触发 Scheduler
2. 调用 local-exec 运行测试
3. 如果测试失败，调用 llm-gateway 分析错误原因
4. 调用 auto-backup 备份错误日志供后续查看

---

## 📊 性能与限制

| 技能 | 响应时间 | 资源占用 | 并发限制 | 注意事项 |
|------|---------|---------|---------|---------|
| llm-unified-gateway | 1-5s | 低 | 10 req/s | 受 API 速率限制 |
| scheduler | < 100ms | 极低 | 5 个并发任务 | 任务文件需定期清理 |
| auto-backup | 5-30s | 中等 | 1 个备份任务 | 大文件备份耗时较长 |
| local-exec | 1-60s | 取决于命令 | 3 个并发命令 | 超时时间可配置 |

---

## 🔧 故障排查

### 常见问题

**Q: llm-gateway 调用失败**
- 检查 API 密钥是否正确配置
- 检查网络连接是否正常
- 查看 `~/.openclaw/llm_gateway.log` 日志

**Q: scheduler 任务不执行**
- 检查 cron 表达式是否正确
- 检查任务是否启用（enabled: true）
- 查看 `~/.openclaw/scheduler.log` 日志

**Q: auto-backup 备份失败**
- 检查磁盘空间是否充足
- 检查备份目录权限
- 查看 `~/.openclaw/backup.log` 日志

**Q: local-exec 权限不足**
- 检查 `permission_level` 配置
- 检查命令是否在白名单中
- 确认路径是否在 `allowed_paths` 中

---

## 📚 最佳实践

### 1. 安全配置
- local-exec 默认使用 `readonly` 权限
- 重要操作开启 `require_confirmation: true`
- 定期查看执行日志

### 2. 成本优化
- llm-gateway 优先使用低成本模型
- 合理设置 `max_retries` 避免重复调用
- 缓存常用查询结果

### 3. 数据安全
- 定期使用 auto-backup 备份
- 重要配置保留多个备份版本
- 备份文件加密存储（可选）

### 4. 性能优化
- Scheduler 任务间隔不要过于密集
- 大文件备份选择系统空闲时间
- 合理设置 `command_timeout` 避免长时间阻塞

---

**最后更新**：2026-03-31
**文档版本**：v1.0.0
