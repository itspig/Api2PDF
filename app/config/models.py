from dataclasses import dataclass, field


@dataclass(slots=True)
class ExportConfig:
    url: str
    output: str | None = None
    max_pages: int = 100
    max_depth: int = 4
    timeout: int = 20
    debug: bool = False
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    no_sitemap: bool = False
    add_column_title: bool = False
    no_images: bool = False

    def validate(self) -> None:
        if self.max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if self.max_depth < 0:
            raise ValueError("max_depth must be 0 or greater")
        if self.timeout < 1:
            raise ValueError("timeout must be at least 1 second")
