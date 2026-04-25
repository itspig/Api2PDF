# api2pdf

`api2pdf` is a Windows-friendly Python CLI that exports API documentation sites into a single offline PDF.

## Features

- Discovers URLs from `sitemap.xml`, `sitemap_index.xml`, and `robots.txt` `Sitemap:` entries.
- Falls back to same-domain BFS crawling when no sitemap is available.
- Filters duplicate URLs, fragments, static assets, auth/search/tag pages, and optional include/exclude patterns.
- Extracts readable documentation text using common docs selectors, `trafilatura`, then cleaned body text.
- The packaged `.exe` uses a stdlib HTML text extractor fallback for better PyInstaller reliability.
- Generates a structured PDF with title page, clickable contents list, per-page PDF bookmarks (with nested headings), dark-theme code blocks with a language ribbon, and tables.

## Install for development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`lxml` is pinned to `5.1.1` because `trafilatura==1.9.0` requires `lxml < 5.2.0`.
`click` is pinned to `8.1.7` because `typer==0.12.3` is not compatible with Click 8.2+/8.3 help rendering APIs.

## Usage

```powershell
python run.py export "http://docs.thinktrader.net/"
python run.py export "http://docs.thinktrader.net/" -o thinktrader.pdf
python run.py export "http://docs.thinktrader.net/pages/" --include "/pages/"
python run.py export "http://docs.thinktrader.net/" --exclude "/changelog" --exclude "/release"
python run.py export "http://docs.thinktrader.net/" --debug
```

Installed console script:

```powershell
api2pdf export "https://example.com/docs/" --max-pages 100 --max-depth 4
api2pdf version
```

## Build single exe

```powershell
.\scripts\build_exe.ps1
```

The executable is written to `dist/api2pdf.exe`.

The build script pins `PyInstaller==6.11.1` for reproducible Windows builds.

## Known limitations

- The first version focuses on readable text, not pixel-perfect webpage styling.
- JavaScript-rendered docs are not supported because Chromium/Playwright is intentionally excluded.
- `robots.txt` crawl-delay/disallow enforcement is not implemented yet; use `--max-pages`, `--max-depth`, and include/exclude filters responsibly.
- Complex site-specific extraction can be added later via adapters.
