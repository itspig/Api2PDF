from pathlib import Path

import httpx

from app.config.models import ExportConfig
from app.core.pipeline import run_export


def test_run_export_with_mocked_sitemap_pipeline(monkeypatch, tmp_path: Path) -> None:
    sitemap = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/docs/index.html</loc></url><url><loc>https://example.com/docs/second.html</loc></url></urlset>"""
    pages = {
        "https://example.com/sitemap.xml": sitemap,
        "https://example.com/docs/index.html": "<html><body><main><h1>Index</h1><p>This mocked API documentation page has enough useful readable text for extraction and PDF output validation.</p></main></body></html>",
        "https://example.com/docs/second.html": "<html><body><article><h1>Second</h1><p>This second mocked API documentation page validates multi-page compilation into the generated PDF.</p></article></body></html>",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://example.com/robots.txt":
            return httpx.Response(404)
        body = pages.get(url)
        if body is None:
            return httpx.Response(404)
        content_type = "application/xml" if url.endswith("sitemap.xml") else "text/html"
        return httpx.Response(200, text=body, headers={"content-type": content_type})

    def client_factory(timeout: int) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True, timeout=timeout, trust_env=False)

    monkeypatch.setattr("app.core.pipeline.create_client", client_factory)
    output = tmp_path / "docs.pdf"
    result = run_export(ExportConfig(url="https://example.com/docs/index.html", output=str(output), max_pages=5))

    assert result == str(output)
    assert output.exists()
    assert output.stat().st_size > 1000
