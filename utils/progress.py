"""Progress reporting types for UI and job tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass(slots=True)
class DownloadResult:
    success: bool
    pdf_path: str | None = None
    title: str | None = None
    page_count: int = 0
    error: str | None = None


@dataclass(slots=True)
class JobState:
    job_id: str
    url: str
    phase: str = "queued"
    message: str = "Waiting to start..."
    current: int = 0
    total: int = 0
    title: str | None = None
    pdf_path: str | None = None
    error: str | None = None
    done: bool = False
    created_at: float = field(default_factory=time.time)
    downloaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        percent = 0
        if self.total > 0:
            percent = min(100, round((self.current / self.total) * 100))
        return {
            "job_id": self.job_id,
            "url": self.url,
            "phase": self.phase,
            "message": self.message,
            "current": self.current,
            "total": self.total,
            "percent": percent,
            "title": self.title,
            "done": self.done,
            "error": self.error,
            "has_pdf": bool(self.pdf_path and self.done and not self.downloaded),
            "downloaded": self.downloaded,
        }

    def update_from_event(self, event: dict[str, Any]) -> None:
        for key in ("phase", "message", "current", "total", "title", "error"):
            if key in event:
                setattr(self, key, event[key])
        if event.get("phase") in {"done", "error"}:
            self.done = True
        if event.get("pdf_path"):
            self.pdf_path = event["pdf_path"]
