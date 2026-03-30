from typing import AsyncGenerator
import httpx
from backend.config import config


class LLMRouter:
    def __init__(self):
        self.provider = config["llm"]["provider"]
        self.model = config["llm"]["model"]
        self.ollama_url = config["llm"].get("ollama_url", "http://localhost:11434")
        self.quality_model = config["llm"].get("quality_model", "ollama")
        self.anthropic_key = config.get("anthropic_api_key", "")
        self.openai_key = config.get("openai_api_key", "")
        self.openai_model = config.get("openai_model", "gpt-4o-mini")

    async def stream(
        self,
        messages: list[dict],
        quality_required: bool = False,
    ) -> AsyncGenerator[str, None]:
        provider = self.quality_model if quality_required else self.provider

        if provider == "ollama":
            async for token in self._stream_ollama(messages):
                yield token
        elif provider == "claude":
            async for token in self._stream_claude(messages):
                yield token
        elif provider == "openai":
            async for token in self._stream_openai(messages):
                yield token
        else:
            raise ValueError(f"Unknown provider: {provider}")

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


llm_router = LLMRouter()
