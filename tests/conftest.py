import pytest

from ai_support_copilot.api.dependencies import Container, reset_container_for_tests
from ai_support_copilot.core.config import Settings


@pytest.fixture(autouse=True)
async def isolated_container(tmp_path):
    settings = Settings(
        postgres_dsn=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        default_llm_provider="fake",
        default_embedding_provider="local",
        default_vectorstore="memory",
        auth_jwt_secret="test-secret",
    )
    container = Container(settings)
    reset_container_for_tests(container)
    await container.startup()
    try:
        yield container
    finally:
        await container.shutdown()
        reset_container_for_tests(None)
