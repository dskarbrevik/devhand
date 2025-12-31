"""Setup command for initial project configuration."""

import re

import typer
from rich.console import Console

from dh.context import get_context
from dh.utils.commands import check_command_exists, check_tool_version, run_command
from dh.utils.config import save_frontend_env, save_backend_env
from dh.utils.prompts import (
    display_error,
    display_info,
    display_step,
    display_success,
    display_warning,
    prompt_confirm,
    prompt_text,
)

app = typer.Typer(help="Setup and installation commands")
console = Console()


@app.command()
def setup():
    """One-time setup of development environment."""
    console.print("\n🚀 [bold]Setting up development environment...[/bold]\n")

    ctx = get_context()

    # Step 1: Detect project type
    display_step(1, "Detecting project structure...")

    if ctx.has_frontend:
        display_success(f"Frontend detected: {ctx.frontend_path}")
    if ctx.has_backend:
        display_success(f"Backend detected: {ctx.backend_path}")

    if not ctx.has_frontend and not ctx.has_backend:
        display_error("No projects detected in workspace")
        display_info("Expected FE: package.json + next.config.ts")
        display_info("Expected BE: pyproject.toml + main.py")
        raise typer.Exit(1)

    # Step 2: Check required tools
    display_step(2, "Checking required tools...")

    tools_ok = True
    if ctx.has_frontend:
        if not check_command_exists("node"):
            display_error("Node.js not installed (required for frontend)")
            tools_ok = False
        else:
            node_version = check_tool_version("node", "--version")
            display_success(f"Node.js: {node_version}")

        if not check_command_exists("npm"):
            display_error("npm not installed (required for frontend)")
            tools_ok = False
        else:
            npm_version = check_tool_version("npm", "--version")
            display_success(f"npm: {npm_version}")

    if ctx.has_backend:
        if not check_command_exists("uv"):
            display_error("uv not installed (required for backend)")
            display_info("Install: curl -LsSf https://astral.sh/uv/install.sh | sh")
            tools_ok = False
        else:
            uv_version = check_tool_version("uv", "--version")
            display_success(f"uv: {uv_version}")

    # Check Docker (optional)
    if check_command_exists("docker"):
        docker_version = check_tool_version("docker", "--version")
        display_success(f"Docker: {docker_version}")
    else:
        display_warning("Docker not found (optional, needed for containerization)")

    if not tools_ok:
        display_error("Please install missing tools and run setup again")
        raise typer.Exit(1)

    # Step 3: Configure database credentials
    display_step(3, "Configuring database credentials...")

    configure_db = prompt_confirm(
        "Configure database (Supabase) credentials?", default=True
    )

    api_url = None
    if configure_db:
        db_url = prompt_text(
            "Database URL (e.g., https://xxx.supabase.co)",
            default=ctx.config.db.url,
        )

        # Extract project ref
        match = re.search(r"https://([^.]+)\.supabase\.co", db_url)
        project_ref = match.group(1) if match else None

        console.print(
            "\nℹ️  Find keys in: Supabase Dashboard > Settings > API", style="blue"
        )
        console.print("   Copy these to Vercel for deployment\n")

        public_key = prompt_text(
            "Public/Anon key (sb_publishable_* or anon JWT) - for Vercel",
            default=ctx.config.db.public_key,
            password=False,
        )

        console.print(
            "\nℹ️  The following are for devhand CLI operations only:", style="blue"
        )
        console.print("   (NOT needed in Vercel deployment)\n")

        secret_key = prompt_text(
            "Secret/Service role key (sb_secret_* or service_role JWT) - for CLI",
            default=ctx.config.db.secret_key,
            password=True,
        )

        db_password = prompt_text(
            "Database password - for migrations",
            default=ctx.config.db.password,
            password=True,
        )

        access_token = prompt_text(
            "Supabase access token - for CLI (from https://supabase.com/dashboard/account/tokens)",
            default=ctx.config.db.access_token,
            password=True,
        )

        # Ask for API URL if backend exists
        if ctx.has_backend:
            # Auto-populate from existing NEXT_PUBLIC_API_URL if available
            default_api_url = ctx.config.deployment.api_url or "http://localhost:8000"
            # Debug: print what we got
            if ctx.config.deployment.api_url:
                console.print(
                    f"[dim]Loaded existing API URL: {ctx.config.deployment.api_url}[/dim]"
                )
            api_url = prompt_text(
                "Backend API URL (for frontend, e.g., Railway URL) - for Vercel",
                default=default_api_url,
            )

        # Ask for Vercel URL if frontend exists
        vercel_url = None
        if ctx.has_frontend:
            console.print(
                "\nℹ️  Deploy to Vercel first, then come back and update this:",
                style="blue",
            )
            vercel_url = prompt_text(
                "Vercel deployment URL (optional, for validation) - https://your-app.vercel.app",
                default=ctx.config.deployment.vercel_url or "",
            )

        # Update config
        ctx.config.db.url = db_url
        ctx.config.db.public_key = public_key
        ctx.config.db.secret_key = secret_key
        ctx.config.db.password = db_password
        ctx.config.db.access_token = access_token
        ctx.config.db.project_ref = project_ref
        if api_url:
            ctx.config.deployment.api_url = api_url
        if vercel_url:
            ctx.config.deployment.vercel_url = vercel_url

        # Save to frontend .env
        if ctx.has_frontend:
            save_frontend_env(ctx.frontend_path, ctx.config, api_url, vercel_url)
            display_success(f"Configuration saved to {ctx.frontend_path}/.env")

        # Save to backend .env
        if ctx.has_backend:
            save_backend_env(ctx.backend_path, ctx.config)
            display_success(f"Configuration saved to {ctx.backend_path}/.env")

    # Step 4: Install dependencies
    display_step(4, "Installing dependencies...")

    if ctx.has_frontend:
        console.print("\n📦 Installing frontend dependencies...")
        try:
            run_command("npm install", cwd=ctx.frontend_path)
            display_success("Frontend dependencies installed")
        except Exception as e:
            display_error(f"Failed to install frontend dependencies: {e}")

    if ctx.has_backend:
        console.print("\n📦 Installing backend dependencies...")
        try:
            run_command("uv sync --dev", cwd=ctx.backend_path)
            display_success("Backend dependencies installed")
        except Exception as e:
            display_error(f"Failed to install backend dependencies: {e}")

    # Step 5: Verify .env files are gitignored
    display_step(5, "Verifying .gitignore...")

    # Check frontend .gitignore
    if ctx.has_frontend:
        fe_gitignore = ctx.frontend_path / ".gitignore"
        if fe_gitignore.exists():
            with open(fe_gitignore) as f:
                content = f.read()
                if ".env" in content:
                    display_success("Frontend .env already gitignored")
                else:
                    display_warning(
                        "Frontend .env not in .gitignore (should be there by default)"
                    )
        else:
            display_warning("Frontend .gitignore not found")

    # Check backend .gitignore
    if ctx.has_backend:
        be_gitignore = ctx.backend_path / ".gitignore"
        if be_gitignore.exists():
            with open(be_gitignore) as f:
                content = f.read()
                if ".env" in content:
                    display_success("Backend .env already gitignored")
                else:
                    display_warning(
                        "Backend .env not in .gitignore (should be there by default)"
                    )
        else:
            display_warning("Backend .gitignore not found")

    # Final message
    console.print("\n✨ [bold green]Setup complete![/bold green]\n")
    console.print("Configuration saved to .env files in each repo")
    console.print("\nNext steps:")
    console.print("  1. Run [bold]dh validate[/bold] to verify everything")
    console.print("  2. Run [bold]dh db migrate[/bold] to initialize database tables")
    console.print("  3. Run [bold]dh dev[/bold] to start development server")


@app.command()
def install():
    """Install project dependencies."""
    ctx = get_context()

    if ctx.has_frontend:
        console.print("📦 Installing frontend dependencies...")
        try:
            run_command("npm install", cwd=ctx.frontend_path)
            display_success("Frontend dependencies installed")
        except Exception as e:
            display_error(f"Failed: {e}")
            raise typer.Exit(1)

    if ctx.has_backend:
        console.print("📦 Installing backend dependencies...")
        try:
            run_command("uv sync --dev", cwd=ctx.backend_path)
            display_success("Backend dependencies installed")
        except Exception as e:
            display_error(f"Failed: {e}")
            raise typer.Exit(1)
