from app.config.models import ExportConfig
from app.parser.filters import deduplicate_and_filter, should_skip_url


def test_should_skip_static_resource() -> None:
    config = ExportConfig(url="https://example.com/docs/")
    assert should_skip_url("https://example.com/docs/app.js", config)


def test_should_skip_other_domain() -> None:
    config = ExportConfig(url="https://example.com/docs/")
    assert should_skip_url("https://other.com/docs/page", config)


def test_include_and_exclude_filters() -> None:
    config = ExportConfig(url="https://example.com/docs/", include=["/docs/"], exclude=["changelog"])
    assert not should_skip_url("https://example.com/docs/intro", config)
    assert should_skip_url("https://example.com/docs/changelog", config)


def test_deduplicate_and_filter() -> None:
    config = ExportConfig(url="https://example.com/docs/")
    urls = ["https://example.com/docs/a#x", "https://example.com/docs/a#y", "https://example.com/docs/b"]
    assert deduplicate_and_filter(urls, config) == ["https://example.com/docs/a", "https://example.com/docs/b"]


def test_directory_style_start_url_not_skipped() -> None:
    """Regression: a URL like /khQuant/tutorial/ becomes /khQuant/tutorial after
    normalize_url, but it must still be considered inside the inferred prefix."""

    config = ExportConfig(url="https://khsci.com/khQuant/tutorial/")
    assert not should_skip_url("https://khsci.com/khQuant/tutorial/", config)
    assert not should_skip_url("https://khsci.com/khQuant/tutorial", config)
    # And paths under that directory still match
    assert not should_skip_url("https://khsci.com/khQuant/tutorial/getting-started.html", config)
    # Sibling directory is rejected because it does not share the prefix
    assert should_skip_url("https://khsci.com/khQuant/api/", config)
