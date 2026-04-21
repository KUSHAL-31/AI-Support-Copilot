from collections.abc import AsyncIterator


class FakeLLMProvider:
    name = "fake"

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        del temperature
        if "Rewrite the user query" in prompt:
            return prompt.split("Query:", 1)[-1].strip().splitlines()[0]
        if "I could not find reliable information" in prompt:
            return "I could not find reliable information in the knowledge base."
        return (
            "Based on the retrieved knowledge base context, the relevant answer is summarized "
            "with citations below. Review the cited sources for operational details."
        )

    async def stream(self, prompt: str, *, temperature: float = 0.0) -> AsyncIterator[str]:
        text = await self.complete(prompt, temperature=temperature)
        for token in text.split(" "):
            yield token + " "
