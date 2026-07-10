"""
AI算力平台适配层 (Platform Adapter)
===================================

为国产开源GPU AI创新生态赛设计的统一LLM调用适配器。
支持多个国产算力平台的无缝切换，通过环境变量配置即可变更后端。

支持的平台:
- Gitee.AI (沐曦 MetaX GPU) - 国产GPU算力，比赛主要平台
- DeepSeek - 国产大模型，备用
- 可扩展: 华为昇腾、寒武纪等

使用方式:
    from backend.llm.platform_adapter import get_llm
    llm = get_llm(platform="gitee_ai")  # 或从环境变量读取
"""

from __future__ import annotations
import os
import logging
from enum import Enum
from functools import lru_cache
from typing import Optional, Dict, Any, List, TYPE_CHECKING

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import BaseMessage
    from langchain_core.outputs import ChatResult
    from langchain_core.callbacks import CallbackManagerForLLMRun
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None  # type: ignore
    BaseChatModel = object  # type: ignore

logger = logging.getLogger(__name__)


class ExtraBodyChatOpenAI(ChatOpenAI):
    """
    扩展 ChatOpenAI，支持 extra_body 参数。

    某些非标准API（如灵枢Lingshu-32B）需要在请求体中传递
    额外参数（如 top_k），这些参数不属于标准 OpenAI API，
    需要放在 HTTP 请求体的 extra_body 字段中。

    Usage:
        llm = ExtraBodyChatOpenAI(
            model="Lingshu-32B",
            base_url="https://api.moark.com/v1",
            api_key="...",
            extra_body={"top_k": -1},
        )
    """

    extra_body: dict | None = None

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """重写 _generate，在 payload 中注入 extra_body。"""
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class Platform(Enum):
    """支持的国产算力平台枚举"""
    LINGSHU = "lingshu"          # Lingshu-32B 医疗大模型 (moark.com)
    GITEE_AI = "gitee_ai"       # Gitee.AI + 沐曦MetaX GPU
    DEEPSEEK = "deepseek"        # DeepSeek (备用)
    LOCAL = "local"              # 本地模型
    CUSTOM = "custom"            # 自定义OpenAI兼容端点


# 平台默认配置
PLATFORM_CONFIGS: Dict[str, Dict[str, Any]] = {
    "lingshu": {
        "name": "Lingshu-32B (灵枢医疗大模型)",
        "base_url": "https://api.moark.com/v1",
        "default_model": "Lingshu-32B",
        "description": "灵枢32B医疗大模型，心理学/医学领域推理能力强，moark.com提供",
        "is_domestic": True,
        "provider": "moark.com",
        "extra_kwargs": {"top_k": -1},
    },
    "gitee_ai": {
        "name": "Gitee.AI (沐曦GPU)",
        "base_url": "https://api.gitee.ai/v1",
        "default_model": "qwen2.5-7b-instruct",
        "description": "国产开源GPU算力平台，由沐曦MetaX GPU提供推理加速",
        "is_domestic": True,
        "provider": "沐曦 MetaX",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "description": "国产大模型，中文能力强，成本低",
        "is_domestic": True,
        "provider": "DeepSeek",
    },
    "local": {
        "name": "本地模型",
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5:7b",
        "description": "本地部署的开源模型",
        "is_domestic": True,
        "provider": "本地",
    },
    "custom": {
        "name": "自定义平台",
        "base_url": "https://your-endpoint/v1",
        "default_model": "default",
        "description": "自定义OpenAI兼容API端点",
        "is_domestic": True,
        "provider": "自定义",
    },
}


class PlatformAdapter:
    """
    国产算力平台统一适配器

    特性:
    - 统一接口，通过 platform 参数切换后端
    - 自动从环境变量读取 API Key 和 Base URL
    - 支持 fallback 机制（主平台不可用时自动切换备用）
    - 记录平台使用统计
    """

    def __init__(
        self,
        platform: str | None = None,
        model: str | None = None,
        streaming: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        # 从环境变量或参数确定平台
        env_platform = os.getenv("AI_PLATFORM", "gitee_ai")
        self.platform = Platform(platform or env_platform)
        self._config = PLATFORM_CONFIGS.get(
            self.platform.value,
            PLATFORM_CONFIGS["gitee_ai"]
        )

        # API Key 和 Base URL 可从环境变量覆盖
        self.api_key = os.getenv(
            f"{self.platform.value.upper()}_API_KEY",
            os.getenv("AI_API_KEY", "")
        )
        self.base_url = os.getenv(
            f"{self.platform.value.upper()}_BASE_URL",
            self._config["base_url"]
        )
        self.model = model or os.getenv(
            f"{self.platform.value.upper()}_MODEL",
            self._config["default_model"]
        )

        self.streaming = streaming
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._fallback_platforms = self._parse_fallback_platforms()

        logger.info(
            f"平台适配器初始化: 平台={self._config['name']}, "
            f"模型={self.model}, GPU={self._config['provider']}"
        )

    def _parse_fallback_platforms(self) -> list[str]:
        """解析备用平台列表"""
        fallback_str = os.getenv("AI_FALLBACK_PLATFORMS", "deepseek")
        return [p.strip() for p in fallback_str.split(",") if p.strip()]

    def create_llm(self) -> BaseChatModel:
        """
        创建 LangChain 兼容的 LLM 实例

        Returns:
            ChatOpenAI 或 ExtraBodyChatOpenAI 实例（OpenAI兼容接口）
        """
        if not _LANGCHAIN_AVAILABLE:
            raise ImportError("langchain_openai 未安装，请运行: pip install langchain-openai")
        if not self.api_key:
            logger.warning(
                f"平台 {self._config['name']} 的 API Key 未设置，"
                f"请设置环境变量 {self.platform.value.upper()}_API_KEY"
            )

        # 平台特有参数（如灵枢的 top_k），通过 extra_body 传递
        extra_kwargs = self._config.get("extra_kwargs", {})

        common_params = {
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key or "sk-placeholder",
            "streaming": self.streaming,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": 60,
            "max_retries": 2,
        }

        if extra_kwargs:
            return ExtraBodyChatOpenAI(
                **common_params,
                extra_body=dict(extra_kwargs),
            )

        return ChatOpenAI(**common_params)

    def create_llm_with_fallback(self) -> BaseChatModel:
        """
        创建带fallback的LLM实例

        当主平台不可用时，自动切换到备用平台。
        """
        # 如果主平台的API Key未配置，直接尝试fallback
        if not self.api_key and self._fallback_platforms:
            for fallback_name in self._fallback_platforms:
                fallback_config = PLATFORM_CONFIGS.get(fallback_name)
                if not fallback_config:
                    continue
                fallback_key = os.getenv(
                    f"{fallback_name.upper()}_API_KEY",
                    os.getenv("AI_API_KEY", "")
                )
                if fallback_key:
                    logger.warning(
                        f"主平台 {self._config['name']} 未配置API Key，"
                        f"切换到备用平台: {fallback_config['name']}"
                    )
                    return ChatOpenAI(
                        model=fallback_config["default_model"],
                        base_url=fallback_config["base_url"],
                        api_key=fallback_key,
                        streaming=self.streaming,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        timeout=60,
                        max_retries=2,
                    )

        return self.create_llm()

    def get_platform_info(self) -> dict:
        """获取当前平台信息"""
        return {
            "platform": self.platform.value,
            "name": self._config["name"],
            "model": self.model,
            "base_url": self.base_url,
            "provider": self._config["provider"],
            "is_domestic": self._config["is_domestic"],
            "gpu_vendor": "沐曦 MetaX" if self.platform == Platform.GITEE_AI else self._config["provider"],
            "streaming": self.streaming,
        }

    @classmethod
    def list_platforms(cls) -> list[dict]:
        """列出所有支持的平台"""
        result = []
        for key, config in PLATFORM_CONFIGS.items():
            env_key = f"{key.upper()}_API_KEY"
            is_configured = bool(
                os.getenv(env_key) or
                (key in ["gitee_ai", "custom"] and os.getenv("AI_API_KEY"))
            )
            result.append({
                "id": key,
                "name": config["name"],
                "description": config["description"],
                "is_domestic": config["is_domestic"],
                "provider": config["provider"],
                "default_model": config["default_model"],
                "is_configured": is_configured,
            })
        return result


# 全局单例缓存
_llm_cache: Dict[str, BaseChatModel] = {}


@lru_cache(maxsize=4)
def get_platform_adapter(
    platform: str | None = None,
    streaming: bool = False,
) -> PlatformAdapter:
    """获取平台适配器（缓存）"""
    return PlatformAdapter(platform=platform, streaming=streaming)


def get_llm(
    platform: str | None = None,
    streaming: bool = False,
    use_fallback: bool = True,
) -> BaseChatModel:
    """
    获取 LLM 实例的统一入口

    Args:
        platform: 平台ID (gitee_ai / deepseek / local / custom)，默认从环境变量读取
        streaming: 是否启用流式输出
        use_fallback: 是否启用fallback机制

    Returns:
        LangChain BaseChatModel 实例

    环境变量配置:
        AI_PLATFORM=gitee_ai           # 主平台
        GITEE_AI_API_KEY=your_key      # Gitee.AI API密钥
        GITEE_AI_BASE_URL=...          # Gitee.AI API地址（可选）
        GITEE_AI_MODEL=qwen2.5-7b      # Gitee.AI 模型名
        DEEPSEEK_API_KEY=your_key      # DeepSeek API密钥（备用）
        AI_FALLBACK_PLATFORMS=deepseek # 备用平台
    """
    cache_key = f"{platform or os.getenv('AI_PLATFORM', 'gitee_ai')}_{streaming}"

    if cache_key not in _llm_cache:
        adapter = PlatformAdapter(platform=platform, streaming=streaming)
        if use_fallback:
            _llm_cache[cache_key] = adapter.create_llm_with_fallback()
        else:
            _llm_cache[cache_key] = adapter.create_llm()
        logger.info(f"LLM实例已初始化: {adapter.get_platform_info()['name']}")

    return _llm_cache[cache_key]


def get_platform_info() -> dict:
    """获取当前平台信息"""
    adapter = get_platform_adapter()
    return adapter.get_platform_info()
