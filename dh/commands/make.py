"""Make commands for generating project artifacts."""

import typer
from rich.console import Console

from dh.context import get_context
from dh.utils.commands import check_command_exists, run_command
from dh.utils.prompts import display_error, display_success

app = typer.Typer(help="Generate project artifacts")
console = Console()


@app.command()
def requirements():
    """Generate requirements.txt from pyproject.toml using uv."""
    if not check_command_exists("uv"):
        display_error("uv not installed. Install it with: pip install uv")
        raise typer.Exit(1)

    ctx = get_context()

    if not ctx.is_backend and not ctx.has_backend:
        display_error("No backend project found")
        raise typer.Exit(1)

    backend_path = ctx.backend_path if ctx.has_backend else ctx.project_root

    console.print("📦 Generating requirements.txt...\n")
    run_command(
        "uv export --no-dev --no-hashes --output-file requirements.txt",
        cwd=backend_path,
    )
    display_success("requirements.txt generated")
