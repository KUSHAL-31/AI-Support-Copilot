import anyio
from fastapi.testclient import TestClient

from ai_support_copilot.api.main import app


def test_upload_enqueues_and_worker_processes_job(isolated_container) -> None:
    client = TestClient(app)
    register_response = client.post(
        "/auth/register",
        json={
            "tenant_id": "jobs-acme",
            "email": "jobs@example.com",
            "password": "VerySecurePassword123!",
        },
    )
    token = register_response.json()["access_token"]

    upload_response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"tenant_id": "jobs-acme"},
        files={
            "file": (
                "runbook.md",
                b"# Runbook\n\nAPI keys are rotated from the admin console.",
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200
    job = upload_response.json()
    assert job["status"] == "pending"

    anyio.run(isolated_container.ingestion.process_next_job)

    status_response = client.get(
        f"/ingestion/jobs/{job['job_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["document_id"]
    assert status_payload["chunks_indexed"] >= 1
