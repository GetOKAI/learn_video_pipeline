from fastapi import FastAPI, BackgroundTasks, HTTPException
from typing import Dict, Any
import time
import traceback
import os

from job_store import JobStore
from run_pipeline import UnifiedPipeline

JOB_STORE_PATH = os.environ.get("JOB_STORE_PATH", "jobs.json")
job_store = JobStore(JOB_STORE_PATH)

app = FastAPI(title="Video Pipeline API")


def _safe_update(job_id: str, updates: Dict[str, Any]):
    try:
        job_store.update_job(job_id, updates)
    except Exception:
        # best-effort logging; don't raise inside background task
        print(f"Failed to update job {job_id}: {traceback.format_exc()}")


def run_job(job_id: str, payload: Dict[str, Any]):
    """Background worker that executes the requested pipeline job."""
    print(f"[worker] Starting job {job_id} (payload={payload})")
    _safe_update(job_id, {"status": "running", "started_at": time.time()})

    try:
        # Dry-run mode - simulate work and return a lightweight result
        if payload.get("dry_run"):
            time.sleep(1)
            result = {"status": "dry-run", "message": "Simulated run (dry_run=True)"}
            _safe_update(job_id, {"status": "completed", "result": result, "finished_at": time.time()})
            print(f"[worker] Completed dry-run job {job_id}")
            return

        # Real execution: initialize pipeline and run requested mode
        pipeline = UnifiedPipeline()

        mode = payload.get("mode", "complete")
        models = payload.get("models")
        limit = payload.get("limit")
        upload_mode = payload.get("upload_mode", "none")

        _safe_update(job_id, {"status": "running", "meta": {"mode": mode, "upload_mode": upload_mode}})

        if mode == "scripts":
            pipeline.run_script_generation_only()
            res = {"message": "scripts completed"}
        elif mode == "videos":
            res = pipeline.run_video_generation_from_enhanced_prompts(
                enhanced_prompts_file=payload.get("enhanced_file", "enhanced_prompts.json"),
                video_models=models,
                limit=limit,
                upload_mode=upload_mode,
            )
        else:
            # complete
            res = pipeline.run_complete_pipeline(video_models=models, limit=limit, upload_mode=upload_mode)

        _safe_update(job_id, {"status": "completed", "result": res, "finished_at": time.time()})
        print(f"[worker] Job {job_id} finished")
    except Exception as e:
        tb = traceback.format_exc()
        _safe_update(job_id, {"status": "failed", "error": str(e), "traceback": tb, "finished_at": time.time()})
        print(f"[worker] Job {job_id} failed: {e}\n{tb}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/trigger")
def trigger(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """Trigger a pipeline job.

    Payload fields (examples):
      - mode: "scripts" | "videos" | "complete" (default: complete)
      - models: list of video model ids (optional)
      - limit: int (optional)
      - upload_mode: "none" | "per-video" | "post"
      - enhanced_file: path to enhanced prompts (for videos mode)
      - dry_run: bool (if true, simulate the job and return quickly)
    """

    job = job_store.create_job({"payload": payload, "status": "queued"})
    job_id = job["id"]
    background_tasks.add_task(run_job, job_id, payload)
    return job


@app.get("/job/{job_id}")
def get_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
