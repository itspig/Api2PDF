from dataclasses import dataclass, field
from typing import Literal


BlockKind = Literal["heading", "paragraph", "code", "table", "image"]


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


@dataclass(slots=True)
class ImageBlock:
    kind: Literal["image"]
    src: str
    alt: str = ""
    # Filled by the pipeline once the image is downloaded; the exporter uses
    # this byte payload directly so renderers don't need to do I/O.
    data: bytes | None = None
    mime_type: str = ""


Block = HeadingBlock | ParagraphBlock | CodeBlock | TableBlock | ImageBlock


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
