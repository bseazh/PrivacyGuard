"""Explicitly configured OpenAI-compatible inference through the LiteLLM SDK."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class LLMSettings:
    model: str
    api_base: str
    api_key: str

    def validate(self) -> None:
        address = urlsplit(self.api_base)
        local = address.hostname in {"localhost", "127.0.0.1", "::1"}
        model_id = self.model.removeprefix("openai/")
        if not self.model.startswith("openai/") or not model_id.strip() or not (model_id.startswith("/") or re.fullmatch(r"[A-Za-z0-9._:-]+", model_id)):
            raise ValueError("仅支持显式 OpenAI-compatible 模型配置")
        if not address.hostname or address.username or address.password or address.query or address.fragment:
            raise ValueError("模型地址无效")
        if address.scheme != "https" and not (local and address.scheme == "http"):
            raise ValueError("非本机模型必须使用 HTTPS")
        if not self.api_key:
            raise ValueError("必须显式配置模型密钥，本机模型可使用 local-only")

    @classmethod
    def from_env(cls) -> LLMSettings:
        settings = cls(os.getenv("PRIVACYGUARD_LLM_MODEL", ""),
                       os.getenv("PRIVACYGUARD_LLM_BASE_URL", ""),
                       os.getenv("PRIVACYGUARD_LLM_API_KEY", ""))
        settings.validate()
        return settings


class LiteLLMAdapter:
    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings.from_env()
        self.settings.validate()

    async def complete(self, messages: list[dict[str, str]]) -> str:
        os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
        import litellm
        from openai import AsyncOpenAI

        litellm.telemetry = False
        litellm.suppress_debug_info = True
        litellm.set_verbose = False
        litellm.turn_off_message_logging = True
        litellm.callbacks = []
        litellm.success_callback = []
        litellm.failure_callback = []
        async with httpx.AsyncClient(trust_env=False, timeout=90, follow_redirects=False) as http_client:
            async with AsyncOpenAI(api_key=self.settings.api_key, base_url=self.settings.api_base,
                                   http_client=http_client, max_retries=0) as client:
                result = await litellm.acompletion(
                    model=self.settings.model, api_base=self.settings.api_base,
                    api_key=self.settings.api_key, client=client, messages=messages,
                    temperature=0, max_tokens=512, stream=False, timeout=90, num_retries=0,
                )
        if not result.choices or result.choices[0].finish_reason != "stop":
            raise ValueError("模型响应未完整结束")
        message = result.choices[0].message
        if message.tool_calls or not isinstance(message.content, str) or not message.content.strip():
            raise ValueError("模型响应为空或包含未批准工具调用")
        if len(message.content) > 20_000:
            raise ValueError("模型响应超限")
        return message.content
