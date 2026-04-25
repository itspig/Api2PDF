from app.parser.extractor import extract_page


HTML_RICH = """
<html><head><title>API Intro</title></head><body>
  <nav>Navigation</nav>
  <article>
    <h1>API Intro</h1>
    <p>This documentation explains authentication, pagination, orders, positions, accounts, and streaming.</p>
    <h2>Authentication</h2>
    <p>Use API keys with HMAC signing.</p>
    <pre><code class="language-python">def login(token: str) -> bool:
    return bool(token)
</code></pre>
    <h2>Endpoints</h2>
    <table>
      <tr><th>Method</th><th>Path</th></tr>
      <tr><td>GET</td><td>/orders</td></tr>
    </table>
  </article>
</body></html>
"""


def test_extract_page_prefers_article_and_returns_blocks() -> None:
    page = extract_page("https://example.com/docs/intro", HTML_RICH)
    assert page.title == "API Intro"
    assert "Navigation" not in page.text
    kinds = [block.kind for block in page.blocks]
    assert "heading" in kinds
    assert "paragraph" in kinds
    assert "code" in kinds
    assert "table" in kinds


def test_extract_page_code_block_preserves_content() -> None:
    page = extract_page("https://example.com/docs/intro", HTML_RICH)
    code_blocks = [block for block in page.blocks if block.kind == "code"]
    assert code_blocks
    assert "def login" in code_blocks[0].text
    assert code_blocks[0].language == "python"


def test_extract_page_table_block_has_rows() -> None:
    page = extract_page("https://example.com/docs/intro", HTML_RICH)
    tables = [block for block in page.blocks if block.kind == "table"]
    assert tables
    assert tables[0].rows[0] == ["Method", "Path"]
    assert tables[0].rows[1] == ["GET", "/orders"]
