from app.parser.extractor import extract_page


def test_extract_page_prefers_article() -> None:
    html = """
    <html><head><title>Ignored</title></head><body>
      <nav>Navigation</nav>
      <article><h1>API Intro</h1><p>This documentation explains authentication, pagination, orders, positions, accounts, and streaming in useful detail.</p></article>
    </body></html>
    """
    page = extract_page("https://example.com/docs/intro", html)
    assert page.title == "API Intro"
    assert "Navigation" not in page.text
    assert "authentication" in page.text
