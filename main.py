#!/usr/bin/env python3
"""FlipHTML5 downloader CLI."""

from __future__ import annotations

import argparse
import asyncio
import sys

from downloader import DownloaderOptions, FlipHTML5Downloader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download FlipHTML5 pages and build a PDF."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="FlipHTML5 book URL (e.g. https://online.fliphtml5.com/ikikw/tvsx/)",
    )
    parser.add_argument(
        "--config",
        default="",
        help="Local config.js path (skips fetching config from the web)",
    )
    parser.add_argument("--out", default="download", help="Output directory")
    parser.add_argument(
        "--workers", type=int, default=6, help="Number of download workers"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files"
    )
    parser.add_argument(
        "--pdf", default="", help="Output PDF path (default: <out>/<title>.pdf)"
    )
    return parser


def _run_downloader(downloader: FlipHTML5Downloader) -> int:
    try:
        return asyncio.run(downloader.run())
    except KeyboardInterrupt:
        print("\nDownload cancelled.", file=sys.stderr)
        return 130
    except RuntimeError as exc:
        print(f"error: runtime failure: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.url:
        print("error: URL is required.", file=sys.stderr)
        return 2

    options = DownloaderOptions(
        out=args.out,
        workers=args.workers,
        overwrite=args.overwrite,
        pdf=args.pdf,
        config=args.config,
    )
    downloader = FlipHTML5Downloader(url=args.url, options=options)
    return _run_downloader(downloader)


if __name__ == "__main__":
    raise SystemExit(main())
