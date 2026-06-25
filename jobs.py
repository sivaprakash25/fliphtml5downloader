"""Background download job manager."""

from __future__ import annotations

import asyncio
import os
import shutil
import time
import uuid
from contextlib import suppress
from typing import Any

from downloader import DownloaderOptions, FlipHTML5Downloader
from utils.progress import JobState

MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "3"))
JOB_SWEEP_SECONDS = int(os.environ.get("JOB_SWEEP_SECONDS", "300"))
JOB_MAX_AGE_SECONDS = int(os.environ.get("JOB_MAX_AGE_SECONDS", "1800"))


class JobCapacityError(Exception):
    """Raised when the server is already processing too many books."""


class JobManager:
    def __init__(self, output_root: str = "download") -> None:
        self.output_root = output_root
        self.jobs: dict[str, JobState] = {}
        self._listeners: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()
        self._running = 0
        self._sweeper_task: asyncio.Task | None = None

    def get(self, job_id: str) -> JobState | None:
        return self.jobs.get(job_id)

    async def subscribe(self, job_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._listeners.setdefault(job_id, []).append(queue)
            job = self.jobs.get(job_id)
            if job is not None:
                await queue.put(job.to_dict())
        return queue

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            listeners = self._listeners.get(job_id, [])
            if queue in listeners:
                listeners.remove(queue)

    async def _broadcast(self, job_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            job = self.jobs.get(job_id)
            if job is not None:
                job.update_from_event(event)
            listeners = list(self._listeners.get(job_id, []))
        for queue in listeners:
            payload = job.to_dict() if job is not None else event
            await queue.put(payload)

    async def start(self, url: str) -> str:
        async with self._lock:
            if self._running >= MAX_CONCURRENT_JOBS:
                raise JobCapacityError(
                    f"Server is busy ({self._running}/{MAX_CONCURRENT_JOBS} jobs). "
                    "Please try again in a few minutes."
                )

        job_id = uuid.uuid4().hex
        job = JobState(job_id=job_id, url=url)
        self.jobs[job_id] = job
        asyncio.create_task(self._run(job_id, url))
        return job_id

    async def start_sweeper(self) -> None:
        if self._sweeper_task is not None:
            return
        self._sweeper_task = asyncio.create_task(self._sweeper_loop())

    async def stop_sweeper(self) -> None:
        if self._sweeper_task is None:
            return
        self._sweeper_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._sweeper_task
        self._sweeper_task = None

    async def _sweeper_loop(self) -> None:
        while True:
            await asyncio.sleep(JOB_SWEEP_SECONDS)
            await self._sweep_stale_jobs()

    async def _sweep_stale_jobs(self) -> None:
        now = time.time()
        stale_ids: list[str] = []
        for job_id, job in list(self.jobs.items()):
            age = now - job.created_at
            if age < JOB_MAX_AGE_SECONDS:
                continue
            stale_ids.append(job_id)
        for job_id in stale_ids:
            await self.cleanup_job(job_id)

    async def cleanup_job(self, job_id: str) -> None:
        async with self._lock:
            job = self.jobs.pop(job_id, None)
            self._listeners.pop(job_id, None)
            out_dir = os.path.join(self.output_root, job_id)

        if job is None and not os.path.isdir(out_dir):
            return

        if os.path.isdir(out_dir):
            await asyncio.to_thread(shutil.rmtree, out_dir, True)

    async def cleanup_after_download(self, job_id: str) -> None:
        async with self._lock:
            job = self.jobs.get(job_id)
            if job is not None:
                job.downloaded = True
                job.pdf_path = None

        await self.cleanup_job(job_id)

    async def _run(self, job_id: str, url: str) -> None:
        out_dir = os.path.join(self.output_root, job_id)
        os.makedirs(out_dir, exist_ok=True)
        pdf_path = os.path.join(out_dir, "book.pdf")
        loop = asyncio.get_running_loop()

        async with self._lock:
            self._running += 1

        def on_progress(event: dict[str, Any]) -> None:
            try:
                running = asyncio.get_running_loop()
                running.create_task(self._broadcast(job_id, event))
            except RuntimeError:
                asyncio.run_coroutine_threadsafe(
                    self._broadcast(job_id, event), loop
                )

        downloader = FlipHTML5Downloader(
            url=url,
            options=DownloaderOptions(
                out=out_dir,
                pdf=pdf_path,
                workers=6,
                quiet=True,
                on_progress=on_progress,
            ),
        )

        try:
            await self._broadcast(
                job_id,
                {
                    "phase": "queued",
                    "message": "Starting download...",
                    "current": 0,
                    "total": 0,
                },
            )

            result = await downloader.run_with_result()
            if result.success and result.pdf_path:
                await self._broadcast(
                    job_id,
                    {
                        "phase": "done",
                        "message": "PDF ready to download",
                        "current": result.page_count,
                        "total": result.page_count,
                        "title": result.title,
                        "pdf_path": result.pdf_path,
                    },
                )
            else:
                await self._broadcast(
                    job_id,
                    {
                        "phase": "error",
                        "message": result.error or "Download failed",
                        "error": result.error or "Download failed",
                    },
                )
                await self.cleanup_job(job_id)
        except Exception as exc:
            await self._broadcast(
                job_id,
                {
                    "phase": "error",
                    "message": str(exc),
                    "error": str(exc),
                },
            )
            await self.cleanup_job(job_id)
        finally:
            async with self._lock:
                self._running = max(0, self._running - 1)
