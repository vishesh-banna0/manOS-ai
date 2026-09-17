"""
File: job_service.py

Purpose:
In-process registry for long-running background jobs.

Flashcard authoring makes many local LLM calls and routinely runs for several
minutes. Holding an HTTP request open for that long means the browser shows a
frozen spinner with no idea whether anything is happening, and proxies or
client timeouts can kill the request mid-run. Jobs are started in a worker
thread instead; the client gets a job id immediately and polls for progress.

Scope: single-process, in-memory. That matches how this app is deployed (one
uvicorn process). Running multiple workers would need Redis or a real task
queue - the API shape here would not have to change.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

# Finished jobs are kept this long so a client that polls slowly still sees the
# result, then dropped so the registry cannot grow without bound.
JOB_RETENTION = timedelta(minutes=30)


class JobAlreadyRunning(ValueError):
    """A workspace already has an authoring job in flight."""


@dataclass
class Job:
    id: str
    kind: str
    key: Optional[str] = None
    status: str = "running"  # running | completed | failed
    stage: str = "starting"
    message: str = ""
    current: int = 0
    total: int = 0
    counters: Dict[str, int] = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        elapsed = (self.finished_at or datetime.utcnow()) - self.started_at
        progress = None
        if self.total:
            progress = round(min(1.0, self.current / self.total), 3)

        return {
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "stage": self.stage,
            "message": self.message,
            "current": self.current,
            "total": self.total,
            "progress": progress,
            "counters": self.counters,
            "elapsed_seconds": int(elapsed.total_seconds()),
            "result": self.result,
            "error": self.error,
        }


class JobRegistry:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.RLock()

    def create(self, kind: str) -> Job:
        self._evict_expired()
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, kind: Optional[str] = None) -> List[dict]:
        with self._lock:
            jobs = list(self._jobs.values())
        if kind:
            jobs = [j for j in jobs if j.kind == kind]
        return [j.to_dict() for j in sorted(jobs, key=lambda j: j.started_at, reverse=True)]

    def update(self, job_id: str, **fields) -> None:
        """Merge progress fields into a job. `counters` is merged, not replaced."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            counters = fields.pop("counters", None)
            for key, value in fields.items():
                setattr(job, key, value)
            if counters:
                job.counters.update(counters)

    def _evict_expired(self) -> None:
        cutoff = datetime.utcnow() - JOB_RETENTION
        with self._lock:
            for job_id in [
                jid
                for jid, job in self._jobs.items()
                if job.finished_at and job.finished_at < cutoff
            ]:
                self._jobs.pop(job_id, None)

    def run_in_background(self, kind: str, target: Callable[["JobHandle"], Any], key: Optional[str] = None) -> Job:
        """
        Start `target` on a worker thread and return its Job immediately.

        `target` receives a JobHandle it uses to report progress. Its return
        value becomes job.result.
        """
        with self._lock:
            if key and any(j.key == key and j.status == "running" for j in self._jobs.values()):
                raise JobAlreadyRunning("Flashcard generation is already running for this workspace. Wait for it to finish before starting another deck.")
            job = self.create(kind)
            job.key = key
        handle = JobHandle(self, job.id)

        def runner():
            try:
                result = target(handle)
                self.update(
                    job.id,
                    status="completed",
                    stage="done",
                    result=result if isinstance(result, dict) else {"result": result},
                    finished_at=datetime.utcnow(),
                )
            except Exception as exc:
                traceback.print_exc()
                self.update(
                    job.id,
                    status="failed",
                    stage="failed",
                    error=str(exc),
                    finished_at=datetime.utcnow(),
                )

        # Daemon: a half-finished authoring run should never block shutdown.
        threading.Thread(target=runner, daemon=True, name=f"job-{kind}-{job.id}").start()
        return job


class JobHandle:
    """Progress reporter handed to a background job's target function."""

    def __init__(self, registry: JobRegistry, job_id: str):
        self._registry = registry
        self.job_id = job_id

    def report(
        self,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        current: Optional[int] = None,
        total: Optional[int] = None,
        **counters: int,
    ) -> None:
        fields: Dict[str, Any] = {}
        if stage is not None:
            fields["stage"] = stage
        if message is not None:
            fields["message"] = message
        if current is not None:
            fields["current"] = current
        if total is not None:
            fields["total"] = total
        if counters:
            fields["counters"] = counters
        self._registry.update(self.job_id, **fields)


jobs = JobRegistry()
