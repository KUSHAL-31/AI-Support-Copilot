from collections.abc import Sequence

import httpx

from ai_support_copilot.core.config import Settings
from ai_support_copilot.core.errors import ProviderError


class OllamaEmbeddingProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_embed_model
        self.dimensions = 768

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=60) as client:
            for text in texts:
                response = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._model, "prompt": text},
                )
                if response.status_code >= 400:
                    raise ProviderError(response.text)
                vectors.append(response.json()["embedding"])
        return vectors
