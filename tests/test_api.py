import time
from fastapi.testclient import TestClient

from api import app


def test_trigger_dry_run():
    client = TestClient(app)

    payload = {"mode": "complete", "dry_run": True}
    resp = client.post("/trigger", json=payload)
    assert resp.status_code == 200
    job = resp.json()
    assert "id" in job
    job_id = job["id"]

    # Poll job until completed (dry-run should finish quickly)
    timeout = 10
    start = time.time()
    final = None
    while time.time() - start < timeout:
        r2 = client.get(f"/job/{job_id}")
        assert r2.status_code == 200
        job_state = r2.json()
        if job_state.get("status") in ("completed", "failed"):
            final = job_state
            break
        time.sleep(0.5)

    assert final is not None, "Job did not complete in time"
    assert final.get("status") == "completed"
    assert final.get("result", {}).get("status") == "dry-run"
