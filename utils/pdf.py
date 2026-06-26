"""PDF helpers."""

from __future__ import annotations

import contextlib
import io
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import img2pdf
import pikepdf
from PIL import Image
from tqdm import tqdm

from utils.text import short_label


class PDFBuildCancelled(Exception):
    pass


def _pdf_settings() -> tuple[int, int, int]:
    quality = int(os.environ.get("PDF_JPEG_QUALITY", "85"))
    quality = max(1, min(quality, 95))
    max_dim = int(os.environ.get("PDF_MAX_DIMENSION", "0"))
    workers = int(os.environ.get("PDF_BUILD_WORKERS", "0"))
    if workers <= 0:
        workers = min(8, os.cpu_count() or 4)
    return quality, max_dim, workers


def _compress_page_image(
    image_path: str,
    jpeg_quality: int,
    max_dimension: int,
) -> bytes:
    with Image.open(image_path) as img:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if max_dimension > 0:
            img.thumbnail(
                (max_dimension, max_dimension),
                Image.Resampling.LANCZOS,
            )
        buf = io.BytesIO()
        img.save(
            buf,
            format="JPEG",
            quality=jpeg_quality,
            optimize=True,
            progressive=True,
        )
        return buf.getvalue()


def build_pdf_from_images(
    image_paths: list[str],
    pdf_path: str,
    title: str | None,
    description: str | None,
    cancel_event: threading.Event | None = None,
    on_page: Callable[[int, int, str], None] | None = None,
) -> None:
    if not image_paths:
        raise ValueError("No images to build PDF")

    pdf_dir = os.path.dirname(pdf_path)
    if pdf_dir:
        os.makedirs(pdf_dir, exist_ok=True)

    jpeg_quality, max_dimension, workers = _pdf_settings()
    total = len(image_paths)
    compressed: list[bytes | None] = [None] * total
    done = 0

    def compress_one(index: int, image_path: str) -> tuple[int, bytes]:
        if cancel_event is not None and cancel_event.is_set():
            raise PDFBuildCancelled("PDF build cancelled")
        data = _compress_page_image(image_path, jpeg_quality, max_dimension)
        return index, data

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(compress_one, index, path)
            for index, path in enumerate(image_paths)
        ]
        pbar_ctx = (
            tqdm(total=total, desc="pdf", unit="page", leave=False)
            if on_page is None
            else contextlib.nullcontext()
        )
        with pbar_ctx as pbar:
            for future in as_completed(futures):
                if cancel_event is not None and cancel_event.is_set():
                    raise PDFBuildCancelled("PDF build cancelled")
                index, data = future.result()
                compressed[index] = data
                done += 1
                label = short_label(os.path.basename(image_paths[index]))
                if pbar is not None:
                    pbar.set_description_str(label)
                    pbar.update(1)
                if on_page is not None:
                    on_page(done, total, label)

    if cancel_event is not None and cancel_event.is_set():
        raise PDFBuildCancelled("PDF build cancelled")

    streams = [io.BytesIO(block) for block in compressed if block is not None]
    try:
        pdf_bytes = img2pdf.convert(*streams)
    except (img2pdf.ImageOpenError, ValueError, TypeError) as exc:
        raise ValueError(f"failed to assemble PDF: {exc}") from exc

    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        if title:
            pdf.docinfo["/Title"] = title
        if description:
            pdf.docinfo["/Subject"] = description
        pdf.save(
            pdf_path,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
