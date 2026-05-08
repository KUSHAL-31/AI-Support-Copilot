from pydantic import SecretStr

from ai_support_copilot.core.config import Settings
from ai_support_copilot.providers.factory import build_llm_provider


def test_builds_anthropic_via_openai_compatible_gateway() -> None:
    provider = build_llm_provider(
        Settings(
            llm_provider="anthropic",
            anthropic_openai_api_key=SecretStr("test-key"),
            anthropic_openai_base_url="https://openrouter.ai/api/v1",
            anthropic_chat_model="anthropic/claude-3.5-sonnet",
        )
    )

    assert provider.name == "anthropic"
