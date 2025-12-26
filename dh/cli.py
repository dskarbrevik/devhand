"""CLI application for App Helper."""

from importlib.metadata import version

import typer
from rich.console import Console

app = typer.Typer(
    name="dh",
    help="CLI tool to improve devX for webapps",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Display version information."""
    if value:
        __version__ = version("devhand")
        console.print(f"[bold blue]dh[/bold blue] version [green]{__version__}[/green]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    App Helper CLI - CLI tool to improve devX for webapps.
    """
    pass


if __name__ == "__main__":
    app()
