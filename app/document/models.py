from dataclasses import dataclass


@dataclass(slots=True)
class ExtractedPage:
    url: str
    title: str
    headings: list[str]
    text: str
    word_count: int


@dataclass(slots=True)
class CompiledDocument:
    site_title: str
    source_url: str
    generated_at: str
    pages: list[ExtractedPage]
