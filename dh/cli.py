"""CLI application for DevHand."""

from importlib.metadata import version

import typer
from rich.console import Console

from dh.commands import build, clean, db, dev, setup, validate

app = typer.Typer(
    name="dh",
    help="CLI tool to improve devX for webapps",
    add_completion=False,
)

console = Console()

# Register individual commands from setup and validate
app.command(name="setup")(setup.setup)
app.command(name="install")(setup.install)
app.command(name="validate")(validate.validate)

# Register individual commands from dev
app.command(name="dev")(dev.dev)
app.command(name="lint")(dev.lint)
app.command(name="format")(dev.format)
app.command(name="test")(dev.test)

# Register individual commands from build and clean
app.command(name="build")(build.build)
app.command(name="run")(build.run)
app.command(name="clean")(clean.clean)

# Register db as a subcommand group (has multiple subcommands)
app.add_typer(db.app, name="db", help="Database management")


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
    DevHand CLI - CLI tool to improve devX for webapps.

    Context-aware commands that detect whether you're working with
    frontend (Next.js) or backend (FastAPI) projects.

    Common commands:
      dh setup     - One-time environment setup
      dh validate  - Check environment health
      dh dev       - Start development server
      dh db migrate - Run database migrations
    """
    pass


if __name__ == "__main__":
    app()
