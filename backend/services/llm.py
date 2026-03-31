from typing import AsyncGenerator
import httpx
from backend.config import config

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"


class LLMRouter:
    def __init__(self):
        llm_cfg = config.get("llm", {})
        self._ready = bool(llm_cfg)
        self.provider = llm_cfg.get("provider", "ollama")
        self.model = llm_cfg.get("model", "llama3.1:8b")
        self.ollama_url = llm_cfg.get("ollama_url", "http://localhost:11434")
        self.quality_model = llm_cfg.get("quality_model", "ollama")
        self.anthropic_key = config.get("anthropic_api_key", "")
        self.openai_key = config.get("openai_api_key", "")
        self.openai_model = config.get("openai_model", "gpt-4o-mini")
        self.gemini_key = config.get("gemini_api_key", "")

    def available_providers(self) -> list[dict]:
        providers = [{"id": "ollama", "label": f"Ollama — {self.model}"}]
        if self.anthropic_key:
            providers.append({"id": "claude", "label": "Claude — Haiku"})
        if self.openai_key:
            providers.append({"id": "openai", "label": f"OpenAI — {self.openai_model}"})
        if self.gemini_key:
            providers.append({"id": "gemini", "label": f"Gemini — {GEMINI_MODEL}"})
        return providers

    async def stream(
        self,
        messages: list[dict],
        quality_required: bool = False,
        provider_override: str | None = None,
    ) -> AsyncGenerator[str, None]:
        if provider_override:
            provider = provider_override
        elif quality_required:
            provider = self.quality_model
        else:
            provider = self.provider

        if provider == "ollama":
            async for token in self._stream_ollama(messages):
                yield token
        elif provider == "claude":
            async for token in self._stream_claude(messages):
                yield token
        elif provider == "openai":
            async for token in self._stream_openai(messages):
                yield token
        elif provider == "gemini":
            async for token in self._stream_gemini(messages):
                yield token
        else:
            async for token in self._stream_ollama(messages):
                yield token

    async def complete(self, messages: list[dict]) -> str:
        """Non-streaming completion using the configured default provider."""
        result = ""
        async for token in self.stream(messages):
            result += token
        return result.strip()

    async def _stream_ollama(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        import ollama
        client = ollama.AsyncClient(host=self.ollama_url)
        async for chunk in await client.chat(
            model=self.model,
            messages=messages,
            stream=True,
        ):
            token = chunk["message"]["content"]
            if token:
                yield token

    async def _stream_claude(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self.anthropic_key)
        system = None
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                filtered.append(m)

        async with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system or "",
            messages=filtered,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _stream_openai(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.openai_key)
        stream = await client.chat.completions.create(
            model=self.openai_model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token

    async def _stream_gemini(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.gemini_key,
            base_url=GEMINI_BASE_URL,
        )
        stream = await client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token


llm_router = LLMRouter()
