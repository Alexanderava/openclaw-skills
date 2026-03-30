---
name: local-exec
description: 安全命令执行器，允许 LLM 在受控环境中执行本地命令，包含命令白名单、权限验证、沙箱隔离等安全机制，支持脚本执行、日志查看、服务管理
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
        "emoji": "⚡",
        "homepage": "https://github.com/openclaw-skills/local-exec",
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

# Local Exec

安全命令执行器，为 OpenClaw 提供受控的本地命令执行能力，在保证安全的前提下让 LLM 能够执行系统命令、管理服务和处理文件。

## 安全特性

### 🛡️ 多重安全防护
- **命令白名单**：只允许预定义的命令和参数
- **权限分级**：支持只读、读写、管理三级权限
- **沙箱隔离**：限制命令执行环境和访问范围
- **输入验证**：严格验证所有命令参数
- **审计日志**：记录所有命令执行历史和结果
- **超时控制**：防止命令长时间执行
- **资源限制**：限制 CPU 和内存使用

### ⚠️ 危险操作防护
- **禁止危险命令**：自动拦截 rm -rf、dd 等危险操作
- **路径限制**：限制可访问的文件系统路径
- **网络限制**：控制网络访问权限
- **环境变量过滤**：清理危险的环境变量
- **特权操作确认**：需要用户确认才能执行特权操作

## 功能特性

### 🎯 支持的命令类型
- **系统信息查询**：查看系统状态、资源使用
- **日志查看**：查看和分析日志文件
- **文件操作**：安全的文件读写、复制、移动
- **服务管理**：启动、停止、重启服务
- **进程管理**：查看和管理进程
- **网络诊断**：ping、curl、netstat 等
- **脚本执行**：执行安全的脚本文件

### 📊 执行控制
- **交互式执行**：支持交互式命令执行
- **结果格式化**：自动格式化命令输出
- **错误处理**：智能的错误分类和处理
- **进度显示**：长时间命令显示进度
- **结果缓存**：缓存常用命令结果

## 使用方法

### 查看系统状态

```
使用 local-exec 查看系统状态：
- 命令：system-info
```

### 查看日志

```
调用 local-exec 查看最新日志：
- 命令：tail-log
- 参数：
  - file: ~/.openclaw/scheduler.log
  - lines: 50
```

### 重启服务

```
使用 local-exec 重启服务：
- 命令：restart-service
- 参数：
  - service: openclaw
- 确认：yes
```

### 执行脚本

```
调用 local-exec 执行脚本：
- 命令：run-script
- 参数：
  - script: /path/to/script.sh
  - args: ["arg1", "arg2"]
```

### 查看磁盘空间

```
使用 local-exec 查看磁盘使用情况
```

## 配置说明

在 `~/.openclaw/openclaw.json` 中配置：

```json
{
  "skills": {
    "entries": {
      "local-exec": {
        "enabled": true,
        "config": {
          "permission_level": "readonly",  # readonly, readwrite, admin
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

## 权限级别

### readonly（只读）
允许命令：
- `cat` - 查看文件内容
- `ls` - 列出目录
- `pwd` - 显示当前路径
- `df` - 查看磁盘空间
- `du` - 查看目录大小
- `ps` - 查看进程
- `top`（简版）- 系统监控
- `ping` - 网络测试
- `curl`（只读）- HTTP 请求
- `tail` - 查看日志
- `grep` - 文本搜索
- `head` - 查看文件开头
- `wc` - 统计行数、字数
- `find`（只读）- 查找文件
- `file` - 查看文件类型
- `stat` - 查看文件状态
- `whoami` - 当前用户
- `uname` - 系统信息
- `date` - 查看日期时间
- `env`（过滤后）- 查看环境变量
- `which` - 查找命令位置
- `history`（过滤后）- 命令历史

### readwrite（读写）
包含只读命令，外加：
- `cp` - 复制文件
- `mv` - 移动文件
- `rm`（限制）- 删除文件（不能删除系统文件）
- `touch` - 创建空文件
- `mkdir` - 创建目录
- `rmdir` - 删除空目录
- `echo` - 输出文本
- `tee`（限制）- 写入文件
- `chmod`（限制）- 修改权限
- `chown`（限制）- 修改所有者
- `ln` - 创建链接
- `zip` - 压缩文件
- `unzip` - 解压文件
- `tar`（限制）- 打包文件
- `gzip` - gzip 压缩
- `gunzip` - gzip 解压

### admin（管理）
包含读写命令，外加：
- `sudo`（需要确认）- 提权执行
- `systemctl`（限制）- 服务管理
- `service`（限制）- 服务管理
- `kill`（限制）- 终止进程
- `pkill`（限制）- 终止进程
- `shutdown`（需要确认）- 关机
- `reboot`（需要确认）- 重启
- `mount`（需要确认）- 挂载设备
- `umount`（需要确认）- 卸载设备
- `ifconfig` - 网络配置
- `iptables`（限制）- 防火墙
- `netstat` - 网络状态
- `ss` - socket 统计
- `lsof` - 打开的文件
- `strace`（限制）- 系统调用跟踪
- `vmstat` - 虚拟内存统计
- `iostat` - IO 统计
- `free` - 内存使用
- `uptime` - 系统运行时间
- `dmesg`（限制）- 内核日志

## 命令白名单

### 系统信息

```yaml
system-info:
  command: "uname -a && uptime && df -h && free -h"
  permission: readonly
  description: "查看系统基本信息"
```

### 查看日志

```yaml
tail-log:
  command: "tail -n {lines} {file}"
  permission: readonly
  params:
    file: {type: string, required: true}
    lines: {type: integer, default: 50}
  description: "查看日志文件末尾"
```

### 重启服务

```yaml
restart-service:
  command: "systemctl restart {service}"
  permission: admin
  params:
    service: {type: string, required: true}
  confirm: true
  description: "重启系统服务"
```

### 查看磁盘空间

```yaml
check-disk:
  command: "df -h {path}"
  permission: readonly
  params:
    path: {type: string, default: "/"}
  description: "查看磁盘空间使用"
```

### 运行脚本

```yaml
run-script:
  command: "{script} {args}"
  permission: readwrite
  params:
    script: {type: string, required: true}
    args: {type: array, default: []}
  validate_script: true
  description: "执行脚本文件"
```

### 清理临时文件

```yaml
cleanup-temp:
  command: "find {path} -name '*.tmp' -type f -mtime +1 -delete"
  permission: readwrite
  params:
    path: {type: string, default: "/tmp"}
  confirm: true
  description: "清理临时文件"
```

### 网络测试

```yaml
test-network:
  command: "ping -c {count} {host} && curl -s -w '\\nHTTP Code: %{http_code}\\n' -o /dev/null {url}"
  permission: readonly
  params:
    host: {type: string, default: "8.8.8.8"}
    count: {type: integer, default: 3}
    url: {type: string, default: "https://www.google.com"}
  description: "测试网络连通性"
```

## CLI 命令

### 查看可用命令

```bash
python exec.py list-commands
```

### 执行命令

```bash
python exec.py execute --command tail-log --params '{"file": "~/.openclaw/scheduler.log", "lines": 100}'
```

### 查看执行历史

```bash
python exec.py history --limit 20
```

### 测试命令

```bash
python exec.py test --command ping --params '{"host": "localhost"}'
```

### 验证权限

```bash
python exec.py check-permission --command rm --permission-level readwrite
```

## 执行日志

所有命令执行都会记录到日志文件：

```
2026-03-31 02:45:00 - INFO - Command executed: tail-log
2026-03-31 02:45:00 - INFO - User: openclaw
2026-03-31 02:45:00 - INFO - Params: {"file": "~/.openclaw/scheduler.log", "lines": 50}
2026-03-31 02:45:01 - INFO - Duration: 120ms
2026-03-31 02:45:01 - INFO - Status: success
2026-03-31 02:45:01 - INFO - Exit code: 0
```

## 错误处理

### 权限不足

```json
{
  "status": "error",
  "error": "Permission denied",
  "message": "Command 'rm -rf /' requires admin permission, current level: readonly"
}
```

### 命令不在白名单

```json
{
  "status": "error",
  "error": "Command not allowed",
  "message": "Command 'dd' is not in the allowed list for permission level 'readonly'"
}
```

### 执行超时

```json
{
  "status": "error",
  "error": "Timeout",
  "message": "Command execution exceeded 60 seconds timeout"
}
```

### 路径访问受限

```json
{
  "status": "error",
  "error": "Path forbidden",
  "message": "Access to path '/etc/passwd' is not allowed"
}
```

## 安全建议

1. **默认使用 readonly 权限**，只在需要时提升权限
2. **重要操作需要确认**，避免误操作
3. **定期审查执行日志**，发现异常行为
4. **限制 allowed_paths**，减少潜在风险
5. **不要存储敏感信息**在命令参数中
6. **使用专用用户**运行 OpenClaw，避免使用 root

## 依赖要求

- Python 3.8+
- pyyaml
- subprocess
- shlex

## 注意事项

⚠️ **警告**：即使有多重安全防护，命令执行仍然存在风险。

- 仔细检查命令参数，避免注入攻击
- 不要在生产环境使用 admin 权限
- 重要系统建议先在测试环境验证
- 保持系统和依赖更新
- 定期备份重要数据

## 许可证

MIT License
