# OpenClaw 原生技能套装

为 OpenClaw AI 执行网关开发的增强型原生技能套装，提供多模型统一调用、定时任务、自动备份和本地命令执行能力。

## 技能列表

### 1. llm-unified-gateway
**多模型统一调用网关**
- 支持 GPT/Gemini/MiniMax-M2.5/GLM-5/本地模型
- 自动切换与负载均衡
- 失败重试与降级策略
- 统一输出格式

### 2. scheduler
**定时任务执行器**
- 支持标准 cron 表达式
- 定时触发技能执行
- 支持技能间联动
- 任务状态持久化

### 3. auto-backup
**自动备份助手**
- 自动备份记忆和对话文件
- 支持定时备份
- 备份到桌面指定目录
- 增量备份与清理

### 4. local-exec
**安全命令执行器**
- LLM 驱动的本地命令执行
- 命令白名单机制
- 权限验证与安全沙箱
- 支持脚本执行、日志查看、服务管理

## 安装方式

```bash
# 克隆到 OpenClaw 技能目录
git clone https://github.com/openclaw-skills/native-skills.git ~/.openclaw/skills/

# 或安装单个技能
clawhub install llm-unified-gateway
clawhub install scheduler
clawhub install auto-backup
clawhub install local-exec
```

## 配置说明

每个技能都有独立的 `config.yaml` 配置文件，请根据需求修改：

- `llm-unified-gateway/config.yaml` - 配置 API 密钥和模型参数
- `scheduler/config.yaml` - 配置任务存储和日志路径
- `auto-backup/config.yaml` - 配置备份目标和频率
- `local-exec/config.yaml` - 配置命令白名单

## 许可证

MIT License - 与 OpenClaw 保持一致

## 贡献

欢迎提交 Issue 和 Pull Request！
