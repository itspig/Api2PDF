"""Regression tests for ad/widget removal from documentation pages."""

from app.parser.extractor import extract_page


HTML_WITH_AD_BLOCK = """
<html><head><title>API Docs</title></head><body>
  <div class="toFixedCopy wxFixed"><img src="/assets/wechat.png" alt="微信扫码联系客服" style="width:30px;"></div>
  <div class="toFixedCopy robot"><img src="/assets/AI.png" alt="智能助手" style="width:30px;"></div>
  <div class="toFixedCopy"><img src="/assets/share.png" alt="分享链接" style="width:30px;"></div>
  <article>
    <h1>API Documentation</h1>
    <p>This is the actual documentation content that should remain in the extracted PDF.</p>
    <img src="/assets/docs-diagram.png" alt="API architecture diagram" />
  </article>
</body></html>
"""


def test_extract_page_removes_ad_blocks_and_images() -> None:
    page = extract_page("https://example.com/docs", HTML_WITH_AD_BLOCK)
    # Ad blocks/images should be stripped from extracted text
    assert "微信扫码联系客服" not in page.text
    assert "智能助手" not in page.text
    assert "分享链接" not in page.text
    # Actual documentation content survives
    assert "API Documentation" in page.text
    assert "actual documentation content" in page.text
    # Legitimate image survives
    image_blocks = [b for b in page.blocks if b.kind == "image"]
    assert len(image_blocks) == 1
    assert image_blocks[0].alt == "API architecture diagram"
    # Ad images are removed
    ad_imgs = [b for b in page.blocks if b.kind == "image" and b.alt in {"微信扫码联系客服", "智能助手", "分享链接"}]
    assert ad_imgs == []
