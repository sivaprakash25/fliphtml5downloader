"""PDF helpers."""

from __future__ import annotations

import contextlib
import io
import os
import threading
from typing import Callable

import img2pdf
import pikepdf
from tqdm import tqdm

from utils.text import short_label


class PDFBuildCancelled(Exception):
    pass


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

    merged = pikepdf.Pdf.new()
    total = len(image_paths)
    try:
        pbar_ctx = (
            tqdm(total=total, desc="pdf", unit="page", leave=False)
            if on_page is None
            else contextlib.nullcontext()
        )
        with pbar_ctx as pbar:
            for index, image_path in enumerate(image_paths, start=1):
                if cancel_event is not None and cancel_event.is_set():
                    raise PDFBuildCancelled("PDF build cancelled")
                label = short_label(os.path.basename(image_path))
                if pbar is not None:
                    pbar.set_description_str(label)
                if on_page is not None:
                    on_page(index, total, label)
                try:
                    page_pdf = img2pdf.convert(image_path)
                    with pikepdf.open(io.BytesIO(page_pdf)) as one_page:
                        merged.pages.extend(one_page.pages)
                except (img2pdf.ImageOpenError, OSError, pikepdf.PdfError) as exc:
                    name = os.path.basename(image_path)
                    raise ValueError(
                        f"failed to process image '{name}': {exc}"
                    ) from exc
                if pbar is not None:
                    pbar.update(1)

            if cancel_event is not None and cancel_event.is_set():
                raise PDFBuildCancelled("PDF build cancelled")
            if title:
                merged.docinfo["/Title"] = title
            if description:
                merged.docinfo["/Subject"] = description
            merged.save(pdf_path)
    except pikepdf.PdfError as exc:
        raise ValueError(str(exc)) from exc
    finally:
        merged.close()
