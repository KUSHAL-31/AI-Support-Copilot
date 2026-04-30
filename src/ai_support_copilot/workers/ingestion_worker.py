import asyncio

from ai_support_copilot.api.dependencies import get_container
from ai_support_copilot.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def main() -> None:
    configure_logging()
    container = get_container()
    await container.startup()
    logger.info(
        "worker_started",
        embedding_provider=container.embeddings.name,
        vector_store=container.vector_store.name,
    )
    try:
        while True:
            try:
                job = await container.ingestion.process_next_job()
                if job:
                    logger.info(
                        "ingestion_job_processed",
                        job_id=str(job.id),
                        tenant_id=job.tenant_id,
                    )
                    continue
            except Exception as exc:
                logger.error("ingestion_job_failed", error=str(exc))
            await asyncio.sleep(5)
    finally:
        await container.shutdown()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
