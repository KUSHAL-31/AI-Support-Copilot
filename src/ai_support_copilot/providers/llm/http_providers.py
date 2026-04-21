from collections.abc import AsyncIterator

import httpx

from ai_support_copilot.core.config import Settings
from ai_support_copilot.core.errors import ProviderError


class OllamaLLMProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_chat_model

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self._base_url}/api/generate", json=payload)
        if response.status_code >= 400:
            raise ProviderError(response.text)
        return str(response.json().get("response", "")).strip()

    async def stream(self, prompt: str, *, temperature: float = 0.0) -> AsyncIterator[str]:
        yield await self.complete(prompt, temperature=temperature)


class OpenAICompatibleLLMProvider:
    def __init__(self, name: str, base_url: str, api_key: str, model: str) -> None:
        self.name = name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions", json=payload, headers=headers
            )
        if response.status_code >= 400:
            raise ProviderError(response.text)
        return str(response.json()["choices"][0]["message"]["content"]).strip()

    async def stream(self, prompt: str, *, temperature: float = 0.0) -> AsyncIterator[str]:
        yield await self.complete(prompt, temperature=temperature)
