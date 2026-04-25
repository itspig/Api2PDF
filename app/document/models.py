from dataclasses import dataclass, field
from typing import Literal


BlockKind = Literal["heading", "paragraph", "code", "table", "image"]


@dataclass(slots=True)
class HeadingBlock:
    level: int
    text: str
    kind: Literal["heading"] = field(default="heading", init=False)


@dataclass(slots=True)
class ParagraphBlock:
    text: str
    kind: Literal["paragraph"] = field(default="paragraph", init=False)


@dataclass(slots=True)
class CodeBlock:
    text: str
    language: str = ""
    kind: Literal["code"] = field(default="code", init=False)


@dataclass(slots=True)
class TableBlock:
    rows: list[list[str]]
    kind: Literal["table"] = field(default="table", init=False)


@dataclass(slots=True)
class ImageBlock:
    src: str
    alt: str = ""
    # Filled by the pipeline once the image is downloaded; the exporter uses
    # this byte payload directly so renderers don't need to do I/O.
    data: bytes | None = None
    mime_type: str = ""
    kind: Literal["image"] = field(default="image", init=False)


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
