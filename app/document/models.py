from dataclasses import dataclass, field
from typing import Literal


BlockKind = Literal["heading", "paragraph", "code", "table"]


@dataclass(slots=True)
class HeadingBlock:
    kind: Literal["heading"]
    level: int
    text: str


@dataclass(slots=True)
class ParagraphBlock:
    kind: Literal["paragraph"]
    text: str


@dataclass(slots=True)
class CodeBlock:
    kind: Literal["code"]
    text: str
    language: str = ""


@dataclass(slots=True)
class TableBlock:
    kind: Literal["table"]
    rows: list[list[str]]


Block = HeadingBlock | ParagraphBlock | CodeBlock | TableBlock


@dataclass(slots=True)
class ExtractedPage:
    url: str
    title: str
    headings: list[str]
    text: str
    word_count: int
    blocks: list[Block] = field(default_factory=list)


@dataclass(slots=True)
class CompiledDocument:
    site_title: str
    source_url: str
    generated_at: str
    pages: list[ExtractedPage]
