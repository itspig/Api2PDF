"""Regression tests for should_follow_link on site-specific hosts."""

from app.config.models import ExportConfig
from app.parser.filters import should_follow_link


def test_follow_link_allows_chapters_on_khsci() -> None:
    config = ExportConfig(url="https://khsci.com/khQuant/chapter1/")
    assert should_follow_link("https://khsci.com/khQuant/chapter2/", config)
    assert should_follow_link("https://khsci.com/khQuant/chapter14/", config)
    assert should_follow_link("https://khsci.com/khQuant/cli/", config)


def test_follow_link_rejects_forum_on_khsci() -> None:
    config = ExportConfig(url="https://khsci.com/khQuant/chapter1/")
    assert not should_follow_link("https://khsci.com/khQuant/forum/", config)
    assert not should_follow_link("https://khsci.com/khQuant/suggestions.php", config)
    assert not should_follow_link("https://khsci.com/khQuant/vip-service/", config)


def test_follow_link_generic_host_uses_normal_skip_logic() -> None:
    config = ExportConfig(url="https://other-site.example/docs/")
    # On generic hosts, should_follow_link falls back to normal skip logic
    assert should_follow_link("https://other-site.example/docs/page1", config)
    assert not should_follow_link("https://other-site.example/docs/app.css", config)
