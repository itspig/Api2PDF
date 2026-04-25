from app.document.models import ExtractedPage
from app.document.titles import column_path, decorate_titles, strip_site_suffix


def _page(title: str, *, headings=None) -> ExtractedPage:
    return ExtractedPage(
        url="https://example.com/x",
        title=title,
        headings=list(headings or []),
        text="",
        word_count=0,
        blocks=[],
    )


def test_strip_site_suffix_drops_common_separator() -> None:
    titles = [
        "1.1 Intro - khQuant",
        "1.2 Setup - khQuant",
        "1.3 Run - khQuant",
        "Standalone",
    ]
    cleaned = strip_site_suffix(titles)
    assert cleaned[0] == "1.1 Intro"
    assert cleaned[1] == "1.2 Setup"
    assert cleaned[2] == "1.3 Run"
    # Page without the shared suffix is left untouched
    assert cleaned[3] == "Standalone"


def test_strip_site_suffix_no_op_when_uncommon() -> None:
    titles = ["A - x", "B - y", "C - z"]
    assert strip_site_suffix(titles) == titles


def test_decorate_titles_default_does_not_prepend_path() -> None:
    pages = [_page("1.1 Intro - khQuant"), _page("1.2 Setup - khQuant")]
    decorate_titles(pages, add_column_title=False)
    assert pages[0].title == "1.1 Intro"
    assert pages[1].title == "1.2 Setup"


def test_decorate_titles_with_flag_prepends_section_path() -> None:
    pages = [_page("1.1 Intro - khQuant"), _page("2.3 Storage - khQuant"), _page("Plain")]
    decorate_titles(pages, add_column_title=True)
    assert pages[0].title == "1. 1.1 Intro"
    assert pages[1].title == "2. 2.3 Storage"
    # Plain titles without a leading number are left untouched
    assert pages[2].title == "Plain"


def test_column_path_extracts_top_section_number() -> None:
    page = _page("3.6 Example")
    assert column_path(page) == "3"
    assert column_path(_page("Plain title")) == ""
