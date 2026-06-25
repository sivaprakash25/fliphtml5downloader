"""URL helpers."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_share_url(url: str) -> str:
    """Normalize a FlipHTML5 book URL to its online viewer base."""
    raw = url.strip()
    if not raw:
        raise ValueError("URL is required")

    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = parsed.netloc.lower()

    if "fliphtml5.com" not in host:
        raise ValueError("URL must be a fliphtml5.com book link")

    path = parsed.path.rstrip("/") + "/"
    if host == "fliphtml5.com" and path.count("/") >= 3:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            path = f"/{parts[0]}/{parts[1]}/"

    if host.startswith("online."):
        base = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
        return base

    if host == "fliphtml5.com":
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            online_host = "online.fliphtml5.com"
            online_path = f"/{parts[0]}/{parts[1]}/"
            return urlunparse((parsed.scheme, online_host, online_path, "", "", ""))

    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
