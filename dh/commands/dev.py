"""Development server commands."""

import typer
from rich.console import Console

from dh.context import get_context
from dh.utils.commands import run_command

app = typer.Typer(help="Development server commands")
console = Console()


@app.command()
def dev():
    """Start development server (auto-detects frontend or backend)."""
    ctx = get_context()

    # Try to detect current context first
    if ctx.is_frontend:
        console.print("🚀 Starting Next.js development server...\n")
        run_command("npm run dev", cwd=ctx.frontend_path)
    elif ctx.is_backend:
        console.print("🚀 Starting FastAPI development server...\n")
        run_command(
            "uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload",
            cwd=ctx.backend_path,
        )
    else:
        # Not in a specific project, check what's available
        if ctx.has_frontend and not ctx.has_backend:
            console.print("🚀 Starting Next.js development server...\n")
            run_command("npm run dev", cwd=ctx.frontend_path)
        elif ctx.has_backend and not ctx.has_frontend:
            console.print("🚀 Starting FastAPI development server...\n")
            run_command(
                "uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload",
                cwd=ctx.backend_path,
            )
        else:
            console.print("❌ Ambiguous: both FE and BE projects found", style="red")
            console.print(
                "Run [bold]dh dev[/bold] from within a specific project directory",
                style="yellow",
            )
            raise typer.Exit(1)


@app.command()
def lint():
    """Run linter (auto-detects frontend or backend)."""
    ctx = get_context()

    if ctx.is_frontend:
        console.print("🔍 Running ESLint...\n")
        run_command("npm run lint", cwd=ctx.frontend_path)
    elif ctx.is_backend:
        console.print("🔍 Running ruff check...\n")
        run_command("uv run ruff check .", cwd=ctx.backend_path)
    else:
        # Run for all projects
        if ctx.has_frontend:
            console.print("🔍 Running ESLint (frontend)...\n")
            run_command("npm run lint", cwd=ctx.frontend_path)
        if ctx.has_backend:
            console.print("🔍 Running ruff check (backend)...\n")
            run_command("uv run ruff check .", cwd=ctx.backend_path)


@app.command()
def format():
    """Format code (auto-detects frontend or backend)."""
    ctx = get_context()

    if ctx.is_frontend:
        console.print("🎨 Formatting frontend code...\n")
        console.print(
            "⚠️  ESLint doesn't support auto-formatting. Use Prettier instead.",
            style="yellow",
        )
    elif ctx.is_backend:
        console.print("🎨 Running ruff format...\n")
        run_command("uv run ruff format .", cwd=ctx.backend_path)
        console.print("🔧 Running ruff check --fix...\n")
        run_command("uv run ruff check --fix .", cwd=ctx.backend_path)
    else:
        # Run for all projects
        if ctx.has_backend:
            console.print("🎨 Running ruff format (backend)...\n")
            run_command("uv run ruff format .", cwd=ctx.backend_path)
            console.print("🔧 Running ruff check --fix (backend)...\n")
            run_command("uv run ruff check --fix .", cwd=ctx.backend_path)
        if ctx.has_frontend:
            console.print(
                "⚠️  Frontend formatting requires Prettier (not included)",
                style="yellow",
            )


@app.command()
def test():
    """Run tests (auto-detects frontend or backend)."""
    ctx = get_context()

    if ctx.is_backend:
        console.print("🧪 Running tests...\n")
        result = run_command("uv run pytest", cwd=ctx.backend_path, check=False)
        # pytest returns exit code 5 when no tests are collected
        if result.returncode == 5:
            console.print("⚠️  No tests found in backend", style="yellow")
            console.print("   Create tests in tests/ directory to enable testing\n")
        elif result.returncode != 0:
            raise typer.Exit(result.returncode)
    elif ctx.is_frontend:
        console.print("🧪 Running tests...\n")
        run_command("npm test", cwd=ctx.frontend_path)
    else:
        # Run for all projects
        if ctx.has_backend:
            console.print("🧪 Running backend tests...\n")
            result = run_command("uv run pytest", cwd=ctx.backend_path, check=False)
            if result.returncode == 5:
                console.print("⚠️  No tests found in backend", style="yellow")
                console.print("   Create tests in tests/ directory to enable testing\n")
            elif result.returncode != 0:
                raise typer.Exit(result.returncode)
        if ctx.has_frontend:
            console.print("🧪 Running frontend tests...\n")
            run_command("npm test", cwd=ctx.frontend_path)
