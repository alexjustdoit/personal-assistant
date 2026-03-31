from typing import AsyncGenerator
import httpx
from backend.config import config

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.0-flash"

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"


class LLMRouter:
    def __init__(self):
        llm_cfg = config.get("llm", {})
        self._ready = bool(llm_cfg)
        self.provider = llm_cfg.get("provider", "ollama")
        self.model = llm_cfg.get("model", "llama3.1:8b")
        self.ollama_url = llm_cfg.get("ollama_url", "http://localhost:11434")
        self.quality_model = llm_cfg.get("quality_model", "ollama")
        # briefing_provider overrides provider for briefing synthesis only
        self.briefing_provider = llm_cfg.get("briefing_provider", "") or self.provider
        self.anthropic_key = config.get("anthropic_api_key", "")
        self.openai_key = config.get("openai_api_key", "")
        self.openai_model = config.get("openai_model", "gpt-5.4-nano")
        self.gemini_key = config.get("gemini_api_key", "")
        self.groq_key = config.get("groq_api_key", "")

    def available_providers(self) -> list[dict]:
        providers = [{"id": "ollama", "label": f"Ollama — {self.model}"}]
        if self.anthropic_key:
            providers.append({"id": "claude", "label": "Claude — Haiku"})
        if self.openai_key:
            providers.append({"id": "openai", "label": f"OpenAI — {self.openai_model}"})
        if self.gemini_key:
            providers.append({"id": "gemini", "label": f"Gemini — {GEMINI_MODEL}"})
        if self.groq_key:
            providers.append({"id": "groq", "label": f"Groq — {GROQ_MODEL}"})
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
        elif provider == "groq":
            async for token in self._stream_groq(messages):
                yield token
        else:
            async for token in self._stream_ollama(messages):
                yield token

    def best_vision_provider(self, preferred: str | None = None) -> str | None:
        """Return the best available vision-capable provider, or None if none configured."""
        if preferred in ("claude", "gemini"):
            if preferred == "claude" and self.anthropic_key:
                return "claude"
            if preferred == "gemini" and self.gemini_key:
                return "gemini"
        if self.anthropic_key:
            return "claude"
        if self.gemini_key:
            return "gemini"
        return None

    async def stream_vision(
        self,
        messages: list[dict],
        image_b64: str,
        media_type: str,
        provider: str | None = None,
    ):
        """Stream a response that includes an image. Routes to a vision-capable provider."""
        vision_provider = provider or self.best_vision_provider()
        if vision_provider == "claude":
            async for token in self._stream_claude_vision(messages, image_b64, media_type):
                yield token
        elif vision_provider == "gemini":
            async for token in self._stream_gemini_vision(messages, image_b64, media_type):
                yield token
        else:
            yield "No vision-capable provider is configured. Please add a Claude or Gemini API key."

    async def complete(self, messages: list[dict], provider: str | None = None) -> str:
        """Non-streaming completion. Uses briefing_provider by default; pass provider to override."""
        result = ""
        async for token in self.stream(messages, provider_override=provider or self.provider):
            result += token
        return result.strip()

    async def complete_briefing(self, messages: list[dict], provider: str | None = None) -> str:
        """Non-streaming completion using the configured briefing provider, or a given override."""
        result = ""
        async for token in self.stream(messages, provider_override=provider or self.briefing_provider):
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

    async def _stream_groq(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.groq_key,
            base_url=GROQ_BASE_URL,
        )
        stream = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token

    async def _stream_claude_vision(
        self, messages: list[dict], image_b64: str, media_type: str
    ) -> AsyncGenerator[str, None]:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self.anthropic_key)
        system = None
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                filtered.append({"role": m["role"], "content": m["content"]})

        # Inject image into the last user message
        if filtered and filtered[-1]["role"] == "user":
            text = filtered[-1]["content"]
            filtered[-1] = {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                    {"type": "text", "text": text or "What's in this image?"},
                ],
            }

        async with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system or "",
            messages=filtered,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _stream_gemini_vision(
        self, messages: list[dict], image_b64: str, media_type: str
    ) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.gemini_key, base_url=GEMINI_BASE_URL)

        messages_copy = [{"role": m["role"], "content": m["content"]} for m in messages]
        # Inject image into the last user message
        for i in range(len(messages_copy) - 1, -1, -1):
            if messages_copy[i]["role"] == "user":
                text = messages_copy[i]["content"]
                messages_copy[i] = {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                        {"type": "text", "text": text or "What's in this image?"},
                    ],
                }
                break

        stream = await client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=messages_copy,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token


llm_router = LLMRouter()
