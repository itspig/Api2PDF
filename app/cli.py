from typing import List, Optional

from typing_extensions import Annotated

import typer

from app.config.models import ExportConfig
from app.core.errors import Api2PdfError
from app.version import __version__

app = typer.Typer(help="Export API documentation websites to a single offline PDF.", no_args_is_help=True)


@app.command()
def export(
    url: Annotated[str, typer.Argument(help="Documentation site entry URL")],
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output PDF path")] = None,
    max_pages: Annotated[int, typer.Option("--max-pages", help="Maximum pages to fetch")] = 100,
    max_depth: Annotated[int, typer.Option("--max-depth", help="Maximum BFS crawl depth")] = 4,
    timeout: Annotated[int, typer.Option("--timeout", help="Request timeout in seconds")] = 20,
    include: Annotated[Optional[List[str]], typer.Option("--include", help="Only include URLs containing this token")] = None,
    exclude: Annotated[Optional[List[str]], typer.Option("--exclude", help="Exclude URLs containing this token")] = None,
    no_sitemap: Annotated[bool, typer.Option("--no-sitemap", help="Disable sitemap discovery")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug output")] = False,
) -> None:
    config = ExportConfig(
        url=url,
        output=output,
        max_pages=max_pages,
        max_depth=max_depth,
        timeout=timeout,
        include=include or [],
        exclude=exclude or [],
        no_sitemap=no_sitemap,
        debug=debug,
    )
    try:
        from app.core.pipeline import run_export

        run_export(config)
    except (Api2PdfError, ValueError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.secho(f"Unexpected error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def version() -> None:
    typer.echo(__version__)
