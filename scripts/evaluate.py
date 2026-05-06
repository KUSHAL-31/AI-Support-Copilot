import asyncio
import json
from pathlib import Path

from ai_support_copilot.api.dependencies import get_container
from ai_support_copilot.domain.models import QueryRequest


async def main() -> None:
    container = get_container()
    dataset_path = Path("examples/eval_dataset.jsonl")
    rows = [json.loads(line) for line in dataset_path.read_text().splitlines() if line.strip()]
    results = []
    for row in rows:
        response = await container.workflow.run(
            QueryRequest(tenant_id=row["tenant_id"], query=row["question"])
        )
        results.append(
            {
                "question": row["question"],
                "expected": row["expected_contains"],
                "answer": response.answer,
                "confidence": response.confidence,
                "passed": row["expected_contains"].lower() in response.answer.lower(),
            }
        )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
