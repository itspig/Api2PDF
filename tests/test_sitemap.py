import httpx

from app.net.sitemap import MAX_SITEMAP_BYTES, parse_sitemap


def test_parse_urlset_sitemap() -> None:
    xml = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/docs/a</loc></url></urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=xml)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert parse_sitemap("https://example.com/sitemap.xml", client) == ["https://example.com/docs/a"]


def test_parse_sitemap_respects_limit() -> None:
    xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/docs/a</loc></url><url><loc>https://example.com/docs/b</loc></url></urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=xml)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert parse_sitemap("https://example.com/sitemap.xml", client, limit=1) == ["https://example.com/docs/a"]


def test_parse_sitemap_rejects_large_content_length() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<urlset />", headers={"content-length": str(MAX_SITEMAP_BYTES + 1)})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert parse_sitemap("https://example.com/sitemap.xml", client) == []


def test_parse_sitemap_index() -> None:
    index = """<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://example.com/sitemap-docs.xml</loc></sitemap></sitemapindex>"""
    urlset = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/docs/a</loc></url></urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("sitemap-docs.xml"):
            return httpx.Response(200, content=urlset)
        return httpx.Response(200, content=index)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert parse_sitemap("https://example.com/sitemap.xml", client) == ["https://example.com/docs/a"]
