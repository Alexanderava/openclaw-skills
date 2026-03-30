---
name: llm-unified-gateway
description: 多模型统一调用网关，支持 GPT/Gemini/MiniMax/GLM 等主流模型的自动切换、负载均衡和失败重试，提供统一的调用接口和输出格式
metadata:
  {
    "openclaw":
      {
        "requires":
          {
            "bins": ["python3", "pip"],
            "env": [],
            "config": [],
          },
        "always": false,
        "emoji": "🤖",
        "homepage": "https://github.com/openclaw-skills/llm-unified-gateway",
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

# LLM Unified Gateway

多模型统一调用网关，为 OpenClaw 提供统一的 LLM 访问接口，支持主流模型的自动切换、负载均衡和智能降级。

## 功能特性

### 🎯 核心功能
- **多模型支持**：GPT、Gemini、MiniMax-M2.5、GLM-5、本地模型
- **智能路由**：根据模型可用性、响应速度自动选择最优模型
- **负载均衡**：Round-robin、权重、优先级等多种策略
- **失败重试**：指数退避重试机制，自动切换备用模型
- **统一格式**：所有模型输出统一格式，便于下游处理

### 🛡️ 智能特性
- **健康检查**：定时检测模型可用性
- **成本优化**：优先使用低成本/免费模型
- **速率限制**：自动处理各模型的速率限制
- **错误分类**：区分临时错误和永久错误

## 使用方法

### 基础调用

通过自然语言调用网关：

```
使用 llm-gateway 生成一段关于 AI 的文本，优先使用 GPT-4
```

### 指定模型（可选）

```
调用 llm-gateway 使用 Gemini 分析这段文本的情感
```

### 多模型对比

```
让 llm-gateway 同时使用 GPT 和 GLM 回答这个问题，对比结果
```

## 配置说明

在 `~/.openclaw/openclaw.json` 中配置：

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

## 环境变量

- `OPENAI_API_KEY` - OpenAI API 密钥
- `GEMINI_API_KEY` - Google Gemini API 密钥
- `MINIMAX_API_KEY` - MiniMax API 密钥
- `GLM_API_KEY` - Zhipu AI GLM API 密钥
- `LOCAL_MODEL_URL` - 本地模型服务地址（可选）

## 返回格式

所有模型返回统一格式：

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

## 错误处理

- 模型不可用时自动切换
- 速率限制时自动等待重试
- 网络错误使用指数退避
- 返回详细错误信息便于调试

## 依赖要求

- Python 3.8+
- requests
- pyyaml
- backoff

## 许可证

MIT License
