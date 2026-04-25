from app.core.pipeline import _extract_page_stdlib


HTML_RICH = """
<html><head><title>Frozen Docs</title></head><body>
  <main>
    <h1>Frozen Docs</h1>
    <p>This is the frozen-mode page used by the packaged executable.</p>
    <h2>Code</h2>
    <pre><code class="language-python">print("hello")
</code></pre>
    <h2>Endpoints</h2>
    <table>
      <tr><th>Verb</th><th>Path</th></tr>
      <tr><td>POST</td><td>/login</td></tr>
    </table>
  </main>
</body></html>
"""


def test_stdlib_extractor_emits_blocks() -> None:
    page = _extract_page_stdlib("https://example.com/frozen", HTML_RICH)
    kinds = [block.kind for block in page.blocks]
    assert "heading" in kinds
    assert "paragraph" in kinds
    assert "code" in kinds
    assert "table" in kinds


def test_stdlib_extractor_code_language_and_text() -> None:
    page = _extract_page_stdlib("https://example.com/frozen", HTML_RICH)
    code_blocks = [block for block in page.blocks if block.kind == "code"]
    assert code_blocks
    assert 'print("hello")' in code_blocks[0].text
    assert code_blocks[0].language == "python"


def test_stdlib_extractor_table_rows() -> None:
    page = _extract_page_stdlib("https://example.com/frozen", HTML_RICH)
    tables = [block for block in page.blocks if block.kind == "table"]
    assert tables
    assert tables[0].rows[0] == ["Verb", "Path"]
    assert tables[0].rows[1] == ["POST", "/login"]
