from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass
class ProviderCapabilities:
    streaming: bool
    tool_calling: bool
    multimodal: bool
    local: bool


class LLMProviderAdapter(ABC):
    name: str

    @abstractmethod
    def health(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, prompt: str, *, mode: str = "fast") -> str:
        raise NotImplementedError


class _HTTPChatAdapter(LLMProviderAdapter):
    def __init__(self, *, name: str, local: bool, base_url: str, model: str, timeout_seconds: float, api_key_env: str | None = None) -> None:
        self.name = name
        self._local = local
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._api_key_env = api_key_env

    def health(self) -> str:
        return "ready"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True, tool_calling=True, multimodal=False, local=self._local)

    async def generate(self, prompt: str, *, mode: str = "fast") -> str:
        if not prompt:
            return f"[{self.name}:{mode}] No explicit prompt provided."

        # Try OpenAI-compatible chat endpoint first.
        chat_resp = await self._call_openai_chat(prompt=prompt, mode=mode)
        if chat_resp:
            return chat_resp

        # llama.cpp native completion fallback.
        completion_resp = await self._call_llamacpp_completion(prompt=prompt, mode=mode)
        if completion_resp:
            return completion_resp

        return f"[{self.name}:{mode}] {prompt}"

    async def _call_openai_chat(self, prompt: str, mode: str) -> str | None:
        headers = {"Content-Type": "application/json"}
        if self._api_key_env:
            token = os.getenv(self._api_key_env)
            if token:
                headers["Authorization"] = f"Bearer {token}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are LAWRENCE assistant backend."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2 if mode == "fast" else 0.4,
            "max_tokens": 32 if mode == "fast" else 96,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/v1/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return str(content)
        except Exception:
            return None

    async def _call_llamacpp_completion(self, prompt: str, mode: str) -> str | None:
        payload = {
            "prompt": prompt,
            "temperature": 0.2 if mode == "fast" else 0.4,
            "n_predict": 256 if mode == "fast" else 512,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/completion", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("content") or data.get("completion")
                if content:
                    return str(content)
        except Exception:
            return None
        return None


class LMStudioAdapter(_HTTPChatAdapter):
    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        super().__init__(name="lmstudio", local=True, base_url=base_url, model=model, timeout_seconds=timeout_seconds)


class LlamaCppAdapter(_HTTPChatAdapter):
    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        super().__init__(name="llamacpp", local=True, base_url=base_url, model=model, timeout_seconds=timeout_seconds)


class GeminiAdapter(_HTTPChatAdapter):
    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        super().__init__(
            name="gemini",
            local=False,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            api_key_env="GEMINI_API_KEY",
        )


class OpenAICompatibleAdapter(_HTTPChatAdapter):
    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        super().__init__(
            name="openai_compatible",
            local=False,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            api_key_env="OPENAI_API_KEY",
        )


class LLMGateway:
    def __init__(
        self,
        provider_order: list[str],
        local_first: bool = True,
        endpoints: dict[str, str] | None = None,
        models: dict[str, str] | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        endpoints = endpoints or {}
        models = models or {}
        self._providers: dict[str, LLMProviderAdapter] = {
            "lmstudio": LMStudioAdapter(endpoints.get("lmstudio", "http://127.0.0.1:1234"), models.get("lmstudio", "local-model"), timeout_seconds),
            "llamacpp": LlamaCppAdapter(endpoints.get("llamacpp", "http://127.0.0.1:8080"), models.get("llamacpp", "local-model"), timeout_seconds),
            "gemini": GeminiAdapter(endpoints.get("gemini", "https://generativelanguage.googleapis.com"), models.get("gemini", "gemini-1.5-flash"), timeout_seconds),
            "openai_compatible": OpenAICompatibleAdapter(endpoints.get("openai_compatible", "https://api.openai.com"), models.get("openai_compatible", "gpt-4o-mini"), timeout_seconds),
        }
        self._order = [p for p in provider_order if p in self._providers]
        self._local_first = local_first

    def provider_health(self) -> dict[str, str]:
        return {name: self._providers[name].health() for name in self._order}

    async def fast_generate(self, prompt: str) -> str:
        provider = self._select(mode="fast")
        return await provider.generate(prompt, mode="fast")

    async def slow_generate(self, prompt: str) -> str:
        provider = self._select(mode="slow")
        return await provider.generate(prompt, mode="slow")

    def _select(self, mode: str) -> LLMProviderAdapter:
        if not self._order:
            raise RuntimeError("No providers configured")
        if self._local_first:
            for name in self._order:
                caps = self._providers[name].capabilities()
                if caps.local:
                    return self._providers[name]
        return self._providers[self._order[0]]
