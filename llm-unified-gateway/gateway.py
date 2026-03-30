#!/usr/bin/env python3
"""
LLM Unified Gateway
多模型统一调用网关
支持 GPT/Gemini/MiniMax/GLM 等主流模型的自动切换、负载均衡和失败重试
"""

import os
import sys
import json
import time
import logging
import requests
import yaml
import backoff
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class ProviderType(Enum):
    """模型提供者类型"""
    OPENAI = "openai"
    GOOGLE = "google"
    MINIMAX = "minimax"
    ZHIPUAI = "zhipuai"
    LOCAL = "local"


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: ProviderType
    api_base: str
    model_name: str
    max_tokens: int
    temperature: float
    cost_per_1k_tokens: float
    enabled: bool
    priority: int
    api_key: Optional[str] = None


@dataclass
class ResponseData:
    """统一响应格式"""
    model: str
    response: str
    usage: Dict[str, int]
    cost: float
    latency_ms: int
    timestamp: str
    provider: str
    status: str = "success"
    error: Optional[str] = None


class BaseProvider:
    """基础提供者类"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = logging.getLogger(f"provider.{config.name}")
        
    def generate(self, prompt: str, **kwargs) -> ResponseData:
        """生成文本"""
        raise NotImplementedError
        
    def health_check(self) -> bool:
        """健康检查"""
        try:
            test_prompt = "Say 'OK' if you can hear me."
            response = self.generate(test_prompt, max_tokens=10)
            return response.status == "success"
        except Exception as e:
            self.logger.warning(f"Health check failed for {self.config.name}: {e}")
            return False


class OpenAIProvider(BaseProvider):
    """OpenAI 提供者"""
    
    def generate(self, prompt: str, **kwargs) -> ResponseData:
        start_time = time.time()
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature)
        }
        
        response = requests.post(
            f"{self.config.api_base}/chat/completions",
            headers=headers,
            json=data,
            timeout=(10, 30)
        )
        
        response.raise_for_status()
        result = response.json()
        
        latency_ms = int((time.time() - start_time) * 1000)
        usage = result.get("usage", {})
        
        # 计算成本
        total_tokens = usage.get("total_tokens", 0)
        cost = (total_tokens / 1000) * self.config.cost_per_1k_tokens
        
        return ResponseData(
            model=self.config.name,
            response=result["choices"][0]["message"]["content"],
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": total_tokens
            },
            cost=cost,
            latency_ms=latency_ms,
            timestamp=datetime.utcnow().isoformat() + "Z",
            provider=self.config.provider.value
        )


class GoogleProvider(BaseProvider):
    """Google Gemini 提供者"""
    
    def generate(self, prompt: str, **kwargs) -> ResponseData:
        start_time = time.time()
        
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature)
            }
        }
        
        url = f"{self.config.api_base}/models/{self.config.model_name}:generateContent?key={self.config.api_key}"
        
        response = requests.post(url, headers=headers, json=data, timeout=(10, 30))
        response.raise_for_status()
        result = response.json()
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Gemini 的 usage 信息
        usage = result.get("usageMetadata", {})
        total_tokens = usage.get("totalTokenCount", 0)
        cost = (total_tokens / 1000) * self.config.cost_per_1k_tokens
        
        return ResponseData(
            model=self.config.name,
            response=result["candidates"][0]["content"]["parts"][0]["text"],
            usage={
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": total_tokens
            },
            cost=cost,
            latency_ms=latency_ms,
            timestamp=datetime.utcnow().isoformat() + "Z",
            provider=self.config.provider.value
        )


class MiniMaxProvider(BaseProvider):
    """MiniMax 提供者"""
    
    def generate(self, prompt: str, **kwargs) -> ResponseData:
        start_time = time.time()
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature)
        }
        
        response = requests.post(
            f"{self.config.api_base}/chat/completions",
            headers=headers,
            json=data,
            timeout=(10, 30)
        )
        
        response.raise_for_status()
        result = response.json()
        
        latency_ms = int((time.time() - start_time) * 1000)
        usage = result.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        cost = (total_tokens / 1000) * self.config.cost_per_1k_tokens
        
        return ResponseData(
            model=self.config.name,
            response=result["choices"][0]["message"]["content"],
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": total_tokens
            },
            cost=cost,
            latency_ms=latency_ms,
            timestamp=datetime.utcnow().isoformat() + "Z",
            provider=self.config.provider.value
        )


class ZhipuAIProvider(BaseProvider):
    """智谱 AI GLM 提供者"""
    
    def generate(self, prompt: str, **kwargs) -> ResponseData:
        start_time = time.time()
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature)
        }
        
        response = requests.post(
            f"{self.config.api_base}/chat/completions",
            headers=headers,
            json=data,
            timeout=(10, 30)
        )
        
        response.raise_for_status()
        result = response.json()
        
        latency_ms = int((time.time() - start_time) * 1000)
        usage = result.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        cost = (total_tokens / 1000) * self.config.cost_per_1k_tokens
        
        return ResponseData(
            model=self.config.name,
            response=result["choices"][0]["message"]["content"],
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": total_tokens
            },
            cost=cost,
            latency_ms=latency_ms,
            timestamp=datetime.utcnow().isoformat() + "Z",
            provider=self.config.provider.value
        )


class LocalProvider(BaseProvider):
    """本地模型提供者"""
    
    def generate(self, prompt: str, **kwargs) -> ResponseData:
        start_time = time.time()
        
        data = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature)
        }
        
        response = requests.post(
            f"{self.config.api_base}/chat/completions",
            json=data,
            timeout=(10, 30)
        )
        
        response.raise_for_status()
        result = response.json()
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return ResponseData(
            model=self.config.name,
            response=result["choices"][0]["message"]["content"],
            usage={
                "prompt_tokens": 0,  # 本地模型可能不提供 token 统计
                "completion_tokens": 0,
                "total_tokens": 0
            },
            cost=0.0,  # 本地模型无成本
            latency_ms=latency_ms,
            timestamp=datetime.utcnow().isoformat() + "Z",
            provider=self.config.provider.value
        )


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, strategy: str = "round_robin", weights: Dict[str, float] = None):
        self.strategy = strategy
        self.weights = weights or {}
        self.round_robin_index = 0
        self.latency_history = {}
        
    def select_model(self, models: List[ModelConfig]) -> ModelConfig:
        """选择模型"""
        # 过滤禁用的模型
        enabled_models = [m for m in models if m.enabled]
        
        if not enabled_models:
            raise ValueError("No enabled models available")
        
        if self.strategy == "round_robin":
            model = enabled_models[self.round_robin_index % len(enabled_models)]
            self.round_robin_index += 1
            return model
            
        elif self.strategy == "priority":
            # 按优先级排序
            return min(enabled_models, key=lambda m: m.priority)
            
        elif self.strategy == "weighted":
            # 权重选择
            total_weight = sum(self.weights.get(m.name, 1.0) for m in enabled_models)
            import random
            r = random.random() * total_weight
            
            current = 0
            for model in enabled_models:
                current += self.weights.get(model.name, 1.0)
                if current >= r:
                    return model
                    
        elif self.strategy == "least_latency":
            # 选择延迟最低的模型
            available_latencies = {m.name: self.latency_history.get(m.name, 0) for m in enabled_models}
            return min(enabled_models, key=lambda m: available_latencies[m.name])
        
        # 默认回退到 round_robin
        return enabled_models[self.round_robin_index % len(enabled_models)]
    
    def record_latency(self, model_name: str, latency_ms: int):
        """记录模型延迟"""
        self.latency_history[model_name] = latency_ms


class LLMGateway:
    """LLM 网关主类"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "config.yaml")
        self.config = self._load_config()
        self.providers = {}
        self.load_balancer = LoadBalancer(
            strategy=self.config.get("load_balancing", {}).get("strategy", "round_robin"),
            weights=self.config.get("load_balancing", {}).get("weights", {})
        )
        self.logger = logging.getLogger("llm_gateway")
        self._setup_logging()
        self._initialize_providers()
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO").upper())
        self.logger.setLevel(level)
        
        formatter = logging.Formatter(log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        
        if log_config.get("file"):
            handler = logging.FileHandler(log_config["file"])
        else:
            handler = logging.StreamHandler()
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def _load_config(self) -> Dict:
        """加载配置"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _initialize_providers(self):
        """初始化提供者"""
        model_configs = self.config.get("models", {})
        
        for model_name, model_config in model_configs.items():
            try:
                provider_type = ProviderType(model_config["provider"])
                
                # 获取 API key
                env_var_name = None
                if provider_type == ProviderType.OPENAI:
                    env_var_name = "OPENAI_API_KEY"
                elif provider_type == ProviderType.GOOGLE:
                    env_var_name = "GEMINI_API_KEY"
                elif provider_type == ProviderType.MINIMAX:
                    env_var_name = "MINIMAX_API_KEY"
                elif provider_type == ProviderType.ZHIPUAI:
                    env_var_name = "GLM_API_KEY"
                elif provider_type == ProviderType.LOCAL:
                    env_var_name = "LOCAL_MODEL_URL"
                
                api_key = os.getenv(env_var_name) if env_var_name else None
                
                config = ModelConfig(
                    name=model_name,
                    provider=provider_type,
                    api_base=model_config["api_base"],
                    model_name=model_config["model_name"],
                    max_tokens=model_config["max_tokens"],
                    temperature=model_config["temperature"],
                    cost_per_1k_tokens=model_config["cost_per_1k_tokens"],
                    enabled=model_config["enabled"],
                    priority=model_config["priority"],
                    api_key=api_key
                )
                
                # 创建提供者实例
                if provider_type == ProviderType.OPENAI:
                    self.providers[model_name] = OpenAIProvider(config)
                elif provider_type == ProviderType.GOOGLE:
                    self.providers[model_name] = GoogleProvider(config)
                elif provider_type == ProviderType.MINIMAX:
                    self.providers[model_name] = MiniMaxProvider(config)
                elif provider_type == ProviderType.ZHIPUAI:
                    self.providers[model_name] = ZhipuAIProvider(config)
                elif provider_type == ProviderType.LOCAL:
                    self.providers[model_name] = LocalProvider(config)
                
                self.logger.info(f"Initialized provider for {model_name}")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize provider for {model_name}: {e}")
    
    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.RequestException, Exception),
        max_tries=lambda: self.config.get("retry", {}).get("max_attempts", 3),
        max_time=lambda: self.config.get("retry", {}).get("max_delay", 60)
    )
    def generate(self, prompt: str, model: str = None, **kwargs) -> ResponseData:
        """
        生成文本
        
        Args:
            prompt: 输入提示
            model: 指定模型名称（可选）
            **kwargs: 额外参数（max_tokens, temperature 等）
        
        Returns:
            ResponseData: 统一格式的响应
        """
        start_time = time.time()
        
        try:
            # 如果指定了模型，直接使用
            if model and model in self.providers:
                selected_model = self._get_model_config(model)
                provider = self.providers[model]
                self.logger.info(f"Using specified model: {model}")
            else:
                # 使用负载均衡选择模型
                model_configs = [self._get_model_config(name) for name in self.providers.keys()]
                selected_model = self.load_balancer.select_model(model_configs)
                provider = self.providers[selected_model.name]
                self.logger.info(f"Selected model by load balancer: {selected_model.name}")
            
            # 生成响应
            response = provider.generate(prompt, **kwargs)
            
            # 记录延迟
            self.load_balancer.record_latency(response.model, response.latency_ms)
            
            self.logger.info(
                f"Generated response using {response.model} "
                f"({response.latency_ms}ms, ${response.cost:.6f})"
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Generation failed: {e}")
            
            # 尝试使用备用模型
            if not model:  # 只有在未指定模型时才尝试备用
                return self._try_fallback_models(prompt, **kwargs)
            
            raise
    
    def _get_model_config(self, model_name: str) -> ModelConfig:
        """获取模型配置"""
        provider = self.providers[model_name]
        return provider.config
    
    def _try_fallback_models(self, prompt: str, **kwargs) -> ResponseData:
        """尝试备用模型"""
        fallback_models = self.config.get("fallback_models", [])
        
        for fallback_model in fallback_models:
            if fallback_model in self.providers:
                try:
                    self.logger.warning(f"Trying fallback model: {fallback_model}")
                    return self.generate(prompt, model=fallback_model, **kwargs)
                except Exception as e:
                    self.logger.error(f"Fallback model {fallback_model} also failed: {e}")
                    continue
        
        raise Exception("All models failed, including fallback models")
    
    def health_check(self) -> Dict[str, bool]:
        """健康检查"""
        results = {}
        for model_name, provider in self.providers.items():
            try:
                results[model_name] = provider.health_check()
            except Exception as e:
                self.logger.error(f"Health check failed for {model_name}: {e}")
                results[model_name] = False
        return results
    
    def get_available_models(self) -> List[str]:
        """获取可用模型列表"""
        return [name for name, provider in self.providers.items() if provider.config.enabled]


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM Unified Gateway CLI")
    parser.add_argument("prompt", help="输入提示")
    parser.add_argument("--model", help="指定模型")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--max-tokens", type=int, help="最大 token 数")
    parser.add_argument("--temperature", type=float, help="采样温度")
    parser.add_argument("--health-check", action="store_true", help="运行健康检查")
    parser.add_argument("--list-models", action="store_true", help="列出可用模型")
    
    args = parser.parse_args()
    
    # 初始化网关
    gateway = LLMGateway(config_path=args.config)
    
    if args.health_check:
        print("Running health check...")
        results = gateway.health_check()
        for model, healthy in results.items():
            status = "✅ Healthy" if healthy else "❌ Unhealthy"
            print(f"{model}: {status}")
        return
    
    if args.list_models:
        models = gateway.get_available_models()
        print("Available models:")
        for model in models:
            print(f"  - {model}")
        return
    
    # 生成响应
    kwargs = {}
    if args.max_tokens:
        kwargs["max_tokens"] = args.max_tokens
    if args.temperature is not None:
        kwargs["temperature"] = args.temperature
    
    try:
        response = gateway.generate(args.prompt, model=args.model, **kwargs)
        print(json.dumps(asdict(response), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
