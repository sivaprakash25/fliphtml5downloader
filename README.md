# FlipHTML5 to PDF Downloader — Free Flipbook PDF Converter

> Download FlipHTML5 flipbooks as PDF online or via CLI. Paste a book URL, fetch pages automatically, and save a single PDF for offline reading.

Convert public [FlipHTML5](https://fliphtml5.com) / [online.fliphtml5.com](https://online.fliphtml5.com) flipbooks to PDF. This open-source **FlipHTML5 downloader** fetches the online `config.js`, decrypts the page list, downloads all page images, and merges them into one PDF.

**Keywords:** fliphtml5 to pdf · fliphtml5 downloader · flipbook pdf converter · download fliphtml5 book · save fliphtml5 offline

Includes a **web UI** (paste URL → live progress → auto-download) and a **CLI** for scripting.

## Features

- Fetches **online `config.js`** automatically (no manual config upload in the web UI)
- Decrypts FlipHTML5's encrypted `fliphtml5_pages` manifest (via official `deString` WASM)
- Downloads high-resolution pages from `files/large/`
- Builds a single PDF with embedded title metadata
- Web UI with real-time progress (Server-Sent Events)
- Auto-downloads the PDF when processing completes
- Deletes server files after download (no long-term storage)
- Concurrent job limit for safe public hosting

## Requirements

- Python **3.10+**
- Internet access to `online.fliphtml5.com` and `static.fliphtml5.com`

## Quick start (Web UI)

### Windows

Double-click `run-ui.bat`, or:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app:app --host 127.0.0.1 --port 8765
```

Open **http://127.0.0.1:8765**, paste a FlipHTML5 URL, and click **Download PDF**.

Stop the server with **Ctrl+C** in the terminal.

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8765
```

## CLI usage

The web UI uses online config only. The CLI can optionally use a local `config.js`:

```bash
# Online config (default)
python main.py "https://online.fliphtml5.com/ikikw/tvsx/" --pdf book.pdf

# Local config.js (optional)
python main.py "https://online.fliphtml5.com/ikikw/tvsx/" --config config.js --pdf book.pdf

# More options
python main.py "https://online.fliphtml5.com/USER/BOOK/" \
  --out download \
  --workers 8 \
  --overwrite \
  --pdf output/book.pdf
```

| Option | Description |
|--------|-------------|
| `url` | FlipHTML5 book URL |
| `--out` | Output directory (default: `download`) |
| `--workers` | Parallel download threads (default: `6`) |
| `--pdf` | Output PDF path |
| `--config` | Local `config.js` path (CLI only) |
| `--overwrite` | Re-download existing page files |

Supported URL formats:

- `https://online.fliphtml5.com/USER/BOOK/`
- `https://online.fliphtml5.com/USER/BOOK/#p=1`
- `https://fliphtml5.com/USER/BOOK/Title` (redirects to online viewer)

## Environment variables

Used by the web app when hosting publicly:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CONCURRENT_JOBS` | `3` | Max books processing at once |
| `JOB_MAX_AGE_SECONDS` | `1800` | Delete abandoned jobs after 30 min |
| `JOB_SWEEP_SECONDS` | `300` | Cleanup check interval |
| `SITE_URL` | *(auto)* | Public site URL for SEO tags |
| `PDF_JPEG_QUALITY` | `85` | JPEG quality when building PDF (1–95; lower = smaller) |
| `PDF_MAX_DIMENSION` | `0` | Max page width/height in px (`0` = original) |
| `PDF_BUILD_WORKERS` | `8` | Parallel threads for PDF compression |

Example:

```bash
export MAX_CONCURRENT_JOBS=2
uvicorn app:app --host 0.0.0.0 --port 8765
```

## Docker

```bash
docker build -t fliphtml5downloader .
docker run -d \
  --name fliphtml5 \
  -p 8765:8765 \
  -e MAX_CONCURRENT_JOBS=3 \
  fliphtml5downloader
```

Open **http://localhost:8765**.

## Deploy on PythonAnywhere

This app needs **outbound internet** to reach FlipHTML5. The free Beginner plan will **not** work (restricted allowlist). Use the **Hacker plan ($5/mo)** or higher.

Replace `YOURUSERNAME` with your PythonAnywhere username:

```bash
# 1. Clone and install
cd ~
git clone https://github.com/YOUR-ORG/fliphtml5downloader.git
cd fliphtml5downloader
mkvirtualenv --python=python3.10 fliphtml5
workon fliphtml5
pip install -r requirements.txt

# 2. Test internet (should print 200)
python -c "import urllib.request; print(urllib.request.urlopen('https://online.fliphtml5.com').status)"

# 3. Deploy ASGI site
pa website create \
  --domain YOURUSERNAME.pythonanywhere.com \
  --command '/home/YOURUSERNAME/.virtualenvs/fliphtml5/bin/uvicorn --app-dir /home/YOURUSERNAME/fliphtml5downloader --uds ${DOMAIN_SOCKET} app:app'

# 4. Reload after updates
pa website reload --domain YOURUSERNAME.pythonanywhere.com
```

Public URL: `https://YOURUSERNAME.pythonanywhere.com`

ASGI docs: [PythonAnywhere ASGI hosting](https://help.pythonanywhere.com/pages/ASGICommandLine/)

## How it works

1. Normalize the book URL to the `online.fliphtml5.com` viewer
2. Fetch `mobile/javascript/config.js` from the book site
3. Decrypt `fliphtml5_pages` if encrypted (FlipHTML5 `deString` WASM)
4. Download each page from `files/large/<hash>.webp`
5. Merge images into a PDF with `img2pdf` + `pikepdf`
6. Serve the PDF to the browser; delete files after download

## Project structure

```
fliphtml5downloader/
├── app.py              # FastAPI web server
├── main.py             # CLI entry point
├── downloader.py       # Core download + PDF logic
├── jobs.py             # Background jobs for web UI
├── static/             # Web UI (HTML, CSS, JS)
├── utils/
│   ├── decode.py       # FlipHTML5 config decryption
│   ├── pdf.py          # PDF assembly
│   ├── progress.py     # Job progress types
│   ├── text.py         # Filename helpers
│   └── url.py          # URL normalization
├── Dockerfile
├── run-ui.bat          # Windows launcher
└── requirements.txt
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `wasmtime` install fails | Use Python 3.10+ on a 64-bit OS |
| Web UI loads but download fails | Check internet access to FlipHTML5 |
| `Server is busy` | Wait — `MAX_CONCURRENT_JOBS` limit reached |
| Port 8765 in use | Stop the old server (Ctrl+C) or use another port |
| PythonAnywhere 403 on fetch | Upgrade from free Beginner to Hacker plan |

## Disclaimer

This tool is for **personal offline use** of content you are legally allowed to access. Many FlipHTML5 books are copyrighted. Do not redistribute downloaded PDFs. This project is not affiliated with FlipHTML5.

## License

No license file is included yet. Add one before publishing if you want others to reuse the code.
