"""Validation commands for checking environment health."""

import json
import subprocess

import typer
from rich.console import Console

from dh.context import get_context
from dh.utils.commands import check_command_exists, check_tool_version
from dh.utils.db import create_db_client
from dh.utils.prompts import display_error, display_success, display_warning

app = typer.Typer(help="Environment validation commands")
console = Console()


@app.command()
def validate(
    deploy: bool = typer.Option(
        False,
        "--deploy",
        help="Validate deployment configuration (backend, Supabase, frontend)",
    ),
):
    """Check if environment is properly configured."""
    if deploy:
        _validate_deployment()
    else:
        _validate_local()


def _validate_local():
    """Validate local development environment."""
    console.print("\n🔍 [bold]Validating development environment...[/bold]\n")

    ctx = get_context()
    issues = []

    # Check frontend
    if ctx.has_frontend:
        console.print("[bold]Frontend:[/bold]")

        # Check Node.js
        if check_command_exists("node"):
            version = check_tool_version("node", "--version")
            display_success(f"Node.js: {version}")
        else:
            display_error("Node.js not installed")
            issues.append("Node.js missing")

        # Check npm
        if check_command_exists("npm"):
            version = check_tool_version("npm", "--version")
            display_success(f"npm: {version}")
        else:
            display_error("npm not installed")
            issues.append("npm missing")

        # Check .env
        if (ctx.frontend_path / ".env").exists():
            display_success(".env exists")
        else:
            display_warning(".env not found - run 'dh setup'")
            issues.append("Frontend .env not configured")

        # Check node_modules
        if (ctx.frontend_path / "node_modules").exists():
            display_success("node_modules exists")
        else:
            display_warning("node_modules not found - run 'dh install'")
            issues.append("Frontend dependencies not installed")

        # Check package.json
        if (ctx.frontend_path / "package.json").exists():
            display_success("package.json exists")
        else:
            display_error("package.json not found")
            issues.append("package.json missing")

        console.print()

    # Check backend
    if ctx.has_backend:
        console.print("[bold]Backend:[/bold]")

        # Check Python
        if check_command_exists("python3"):
            version = check_tool_version("python3", "--version")
            display_success(f"Python: {version}")
        else:
            display_error("Python 3 not installed")
            issues.append("Python 3 missing")

        # Check uv
        if check_command_exists("uv"):
            version = check_tool_version("uv", "--version")
            display_success(f"uv: {version}")
        else:
            display_error("uv not installed")
            issues.append("uv missing")

        # Check .env
        if (ctx.backend_path / ".env").exists():
            display_success(".env exists")
        else:
            display_warning(".env not found (optional for backend)")

        # Check .venv
        if (ctx.backend_path / ".venv").exists():
            display_success(".venv exists")
        else:
            display_warning(".venv not found - run 'dh install'")
            issues.append("Backend virtual environment not created")

        # Check pyproject.toml
        if (ctx.backend_path / "pyproject.toml").exists():
            display_success("pyproject.toml exists")
        else:
            display_error("pyproject.toml not found")
            issues.append("pyproject.toml missing")

        console.print()

    # Check Docker (optional)
    console.print("[bold]Optional Tools:[/bold]")
    if check_command_exists("docker"):
        version = check_tool_version("docker", "--version")
        display_success(f"Docker: {version}")
    else:
        display_warning("Docker not installed (optional)")

    console.print()

    # Check database configuration
    console.print("[bold]Database Configuration:[/bold]")
    if ctx.config.db.url:
        display_success(f"Database URL configured: {ctx.config.db.url}")

        # Test connection
        if ctx.config.db.secret_key:
            try:
                db_client = create_db_client(
                    ctx.config.db.url,
                    ctx.config.db.secret_key,
                    ctx.config.db.password,
                    ctx.config.db.project_ref,
                )
                if db_client.test_connection():
                    display_success("Database connection successful")
                else:
                    display_error("Database connection failed")
                    issues.append("Cannot connect to database")
            except Exception as e:
                display_error(f"Database connection error: {e}")
                issues.append("Database connection error")
        else:
            display_warning("Secret key not configured")
            issues.append("Database credentials incomplete")
    else:
        display_warning("Database not configured - run 'dh setup'")
        issues.append("Database not configured")

    # Summary
    console.print()
    if issues:
        console.print(f"[bold yellow]⚠️  Found {len(issues)} issue(s):[/bold yellow]")
        for issue in issues:
            console.print(f"  - {issue}")
        console.print("\nRun [bold]dh setup[/bold] to fix configuration issues")
        raise typer.Exit(1)
    else:
        console.print("✨ [bold green]All checks passed![/bold green]")


def _validate_deployment():
    """Validate deployment configuration for production."""
    console.print("\n🚀 [bold]Validating deployment configuration...[/bold]\n")

    ctx = get_context()
    issues = []

    # First check if local environment is configured
    console.print("[bold]Step 0: Local Environment[/bold]")
    if not (ctx.frontend_path / ".env").exists():
        display_error("Local environment not configured")
        issues.append("Run 'dh setup' first to configure local environment")
        console.print()
        console.print(
            "[bold red]❌ Cannot validate deployment without local setup[/bold red]"
        )
        raise typer.Exit(1)

    display_success("Local environment configured")
    console.print()

    # Load environment variables
    env_vars = _load_env_vars(ctx.frontend_path / ".env")

    # Step 1: Check Backend API (Railway)
    console.print("[bold]Step 1: Backend API (Railway)[/bold]")
    backend_url = env_vars.get("NEXT_PUBLIC_API_URL")

    if not backend_url:
        display_error("Backend API URL not configured in .env")
        issues.append("Backend API URL missing")
    elif "localhost" in backend_url or "127.0.0.1" in backend_url:
        display_warning(f"Backend URL is localhost: {backend_url}")
        display_warning("This looks like local development, not production")
        issues.append("Backend not deployed - still using localhost")
    else:
        display_success(f"Backend URL configured: {backend_url}")

        # Try to curl the backend
        try:
            result = subprocess.run(
                ["curl", "-s", "-f", "-m", "10", backend_url],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    if response.get("status") == "success":
                        display_success("✓ Backend API is accessible and responding")
                    else:
                        display_success(f"Backend responded: {result.stdout[:100]}")
                except json.JSONDecodeError:
                    display_success("Backend is accessible (non-JSON response)")
            else:
                display_error("Backend API is not accessible")
                display_error(f"curl failed with exit code {result.returncode}")
                issues.append("Backend API deployment not accessible")
        except subprocess.TimeoutExpired:
            display_error("Backend API request timed out")
            issues.append("Backend API timeout")
        except Exception as e:
            display_error(f"Error checking backend: {e}")
            issues.append("Backend check failed")

    console.print()

    # Step 2: Check Supabase Configuration
    console.print("[bold]Step 2: Supabase Project[/bold]")
    supabase_url = env_vars.get("NEXT_PUBLIC_SUPABASE_URL")
    supabase_key = env_vars.get("NEXT_PUBLIC_SUPABASE_KEY")

    if not supabase_url:
        display_error("Supabase URL not configured")
        issues.append("Supabase URL missing")
    else:
        display_success(f"Supabase URL configured: {supabase_url}")

        # Check if URL is valid format
        if (
            not supabase_url.startswith("https://")
            or ".supabase.co" not in supabase_url
        ):
            display_warning("Supabase URL format looks incorrect")
            issues.append("Supabase URL format invalid")

    if not supabase_key:
        display_error("Supabase anon key not configured")
        issues.append("Supabase anon key missing")
    else:
        display_success("Supabase anon key configured")

    # Check database connection
    if ctx.config.db.url and ctx.config.db.secret_key:
        try:
            db_client = create_db_client(
                ctx.config.db.url,
                ctx.config.db.secret_key,
                ctx.config.db.password,
                ctx.config.db.project_ref,
            )
            if db_client.test_connection():
                display_success("✓ Supabase database connection successful")

                # Check if allowed_users table exists
                try:
                    db_client.table("allowed_users").select("*").limit(1).execute()
                    display_success("✓ allowed_users table exists")
                except Exception:
                    display_error("allowed_users table not found")
                    display_error("Run 'dh db setup' to create the table")
                    issues.append("Database not set up")
            else:
                display_error("Supabase database connection failed")
                issues.append("Cannot connect to Supabase")
        except Exception as e:
            display_error(f"Supabase connection error: {e}")
            issues.append("Supabase connection failed")
    else:
        display_warning("Supabase credentials incomplete - cannot test database")
        issues.append("Supabase credentials missing")

    console.print()

    # Step 3: Check Frontend Deployment (Vercel)
    console.print("[bold]Step 3: Frontend Deployment (Vercel)[/bold]")
    console.print("This checks if your frontend is configured for deployment.")
    console.print(
        "Note: This cannot verify if you've actually deployed to Vercel yet.\n"
    )

    # Check if all required env vars are set
    required_vars = [
        "NEXT_PUBLIC_SUPABASE_URL",
        "NEXT_PUBLIC_SUPABASE_KEY",
        "NEXT_PUBLIC_API_URL",
    ]

    missing_vars = [var for var in required_vars if not env_vars.get(var)]

    if missing_vars:
        display_error(f"Missing environment variables: {', '.join(missing_vars)}")
        issues.append("Environment variables incomplete")
    else:
        display_success("All required environment variables configured")

    # Check if package.json exists (for Vercel deployment)
    if ctx.has_frontend:
        if (ctx.frontend_path / "package.json").exists():
            display_success("package.json exists (required for Vercel)")
        else:
            display_error("package.json not found")
            issues.append("package.json missing")

        if (ctx.frontend_path / "next.config.ts").exists():
            display_success("next.config.ts exists")
        else:
            display_warning("next.config.ts not found")

    console.print()

    # Summary
    console.print("[bold]Deployment Checklist:[/bold]")
    console.print("✓ Step 1: Deploy Backend to Railway")
    console.print("✓ Step 2: Create & Configure Supabase Project")
    console.print("✓ Step 3: Setup Supabase Database (dh db setup)")
    console.print("✓ Step 4: Configure Local Environment (dh setup)")
    console.print("✓ Step 5: Deploy Frontend to Vercel")
    console.print()

    if issues:
        console.print(
            f"[bold yellow]⚠️  Found {len(issues)} deployment issue(s):[/bold yellow]"
        )
        for issue in issues:
            console.print(f"  - {issue}")
        console.print()
        console.print(
            "📖 See deployment guide: https://github.com/dskarbrevik/devhand/blob/main/DEPLOYMENT_GUIDE.md"
        )
        raise typer.Exit(1)
    else:
        console.print("✨ [bold green]All deployment checks passed![/bold green]")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("1. Deploy to Vercel if you haven't already")
        console.print("2. Add your Vercel URL to Supabase redirect URLs")
        console.print("3. Test the full authentication flow in production")


def _load_env_vars(env_path) -> dict:
    """Load environment variables from .env file."""
    env_vars = {}
    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        pass
    return env_vars
