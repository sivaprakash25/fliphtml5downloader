"""Web UI for FlipHTML5 downloader."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jobs import JobCapacityError, JobManager

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
DOWNLOAD_DIR = APP_DIR / "download"
DOWNLOAD_DIR.mkdir(exist_ok=True)

job_manager = JobManager(output_root=str(DOWNLOAD_DIR))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await job_manager.start_sweeper()
    yield
    await job_manager.stop_sweeper()
    for job_id in list(job_manager.jobs):
        await job_manager.cleanup_job(job_id)


app = FastAPI(title="FlipHTML5 Downloader", version="1.0.0", lifespan=lifespan)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class StartJobRequest(BaseModel):
    url: str = Field(..., min_length=8, description="FlipHTML5 book URL")


class StartJobResponse(BaseModel):
    job_id: str


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="UI files missing")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.post("/api/jobs", response_model=StartJobResponse)
async def start_job(body: StartJobRequest) -> StartJobResponse:
    url = body.url.strip()
    if "fliphtml5.com" not in url.lower():
        raise HTTPException(status_code=400, detail="Please enter a valid FlipHTML5 URL")
    try:
        job_id = await job_manager.start(url)
    except JobCapacityError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return StartJobResponse(job_id=job_id)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    if job_manager.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        queue = await job_manager.subscribe(job_id)
        try:
            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload)}\n\n"
                if payload.get("done"):
                    break
        finally:
            await job_manager.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/jobs/{job_id}/file")
async def download_file(job_id: str, background_tasks: BackgroundTasks) -> FileResponse:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.downloaded:
        raise HTTPException(status_code=410, detail="PDF already downloaded and removed")
    if not job.done or not job.pdf_path:
        raise HTTPException(status_code=409, detail="PDF is not ready yet")
    if not Path(job.pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF file missing")

    filename = "flipbook.pdf"
    if job.title:
        safe = "".join(
            ch if ch.isalnum() or ch in (" ", "-", "_") else "_" for ch in job.title
        ).strip().replace(" ", "_")
        if safe:
            filename = f"{safe}.pdf"

    background_tasks.add_task(job_manager.cleanup_after_download, job_id)
    return FileResponse(
        job.pdf_path,
        media_type="application/pdf",
        filename=filename,
    )
