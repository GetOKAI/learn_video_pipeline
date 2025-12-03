import json
import threading
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any


class JobStore:
    def __init__(self, path: str = "jobs.json"):
        self.path = path
        self.lock = threading.Lock()
        # ensure file exists
        if not os.path.exists(self.path):
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def _read_all(self) -> Dict[str, Any]:
        with open(self.path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}

    def _write_all(self, data: Dict[str, Any]):
        tmp = f"{self.path}.tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def create_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "payload": payload.get("payload") if isinstance(payload, dict) and "payload" in payload else payload,
            "status": payload.get("status", "queued") if isinstance(payload, dict) else "queued",
            "created_at": datetime.utcnow().isoformat(),
        }
        with self.lock:
            all_jobs = self._read_all()
            all_jobs[job_id] = job
            self._write_all(all_jobs)
        return job

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self.lock:
            all_jobs = self._read_all()
            job = all_jobs.get(job_id)
            if not job:
                return None
            job.update(updates)
            all_jobs[job_id] = job
            self._write_all(all_jobs)
        return job

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            all_jobs = self._read_all()
            return all_jobs.get(job_id)

    def list_jobs(self) -> Dict[str, Any]:
        return self._read_all()
