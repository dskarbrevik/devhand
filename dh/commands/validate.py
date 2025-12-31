"""Validation commands for checking environment health."""

import json
import subprocess

import typer
from rich.console import Console

from dh.context import get_context
from dh.utils.commands import check_command_exists, check_tool_version
from dh.utils.db import create_db_client
from dh.utils.prompts import (
    display_error,
    display_info,
    display_success,
    display_warning,
)

app = typer.Typer(help="Environment validation commands")
console = Console()


@app.command()
def validate():
    """Check if environment is properly configured for local development and deployment."""
    console.print("\n🔍 [bold]Validating environment...[/bold]\n")

    ctx = get_context()
    local_issues = []
    deployment_issues = []

    # ============================================
    # PART 1: LOCAL DEVELOPMENT VALIDATION
    # ============================================
    console.print("[bold cyan]═══ Local Development Environment ═══[/bold cyan]\n")

    # Check frontend
    if ctx.has_frontend:
        console.print("[bold]Frontend:[/bold]")

        # Check Node.js
        if check_command_exists("node"):
            version = check_tool_version("node", "--version")
            display_success(f"Node.js: {version}")
        else:
            display_error("Node.js not installed")
            local_issues.append("Node.js missing")

        # Check npm
        if check_command_exists("npm"):
            version = check_tool_version("npm", "--version")
            display_success(f"npm: {version}")
        else:
            display_error("npm not installed")
            local_issues.append("npm missing")

        # Check .env
        env_file_exists = (ctx.frontend_path / ".env").exists()
        if env_file_exists:
            display_success(".env exists")
        else:
            display_warning(".env not found - run 'dh setup'")
            local_issues.append("Frontend .env not configured")

        # Check node_modules
        if (ctx.frontend_path / "node_modules").exists():
            display_success("node_modules exists")
        else:
            display_warning("node_modules not found - run 'npm install'")
            local_issues.append("Frontend dependencies not installed")

        # Check package.json
        if (ctx.frontend_path / "package.json").exists():
            display_success("package.json exists")
        else:
            display_error("package.json not found")
            local_issues.append("package.json missing")

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
            local_issues.append("Python 3 missing")

        # Check uv
        if check_command_exists("uv"):
            version = check_tool_version("uv", "--version")
            display_success(f"uv: {version}")
        else:
            display_error("uv not installed")
            local_issues.append("uv missing")

        # Check .env
        if (ctx.backend_path / ".env").exists():
            display_success(".env exists")
        else:
            display_warning(".env not found (optional for backend)")

        # Check .venv
        if (ctx.backend_path / ".venv").exists():
            display_success(".venv exists")
        else:
            display_warning(".venv not found - run 'make setup'")
            local_issues.append("Backend virtual environment not created")

        # Check pyproject.toml
        if (ctx.backend_path / "pyproject.toml").exists():
            display_success("pyproject.toml exists")
        else:
            display_error("pyproject.toml not found")
            local_issues.append("pyproject.toml missing")

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
    console.print("[bold]Database:[/bold]")
    if ctx.config.db.url:
        display_success(f"Database URL: {ctx.config.db.url}")

        # Test connection
        if ctx.config.db.secret_key:
            try:
                db_client = create_db_client(
                    ctx.config.db.url,
                    ctx.config.db.secret_key,
                    ctx.config.db.password,
                    ctx.config.db.project_ref,
                    ctx.config.db.access_token,  # Pass access token for Management API
                )
                if db_client.test_connection():
                    display_success("Database connection successful")

                    # Check if allowed_users table exists
                    if db_client.table_exists("allowed_users"):
                        display_success("allowed_users table exists")
                    else:
                        display_warning(
                            "allowed_users table not found - run 'dh db migrate'"
                        )
                        deployment_issues.append(
                            "Database not set up (run 'dh db migrate')"
                        )

                    # Check authentication configuration
                    console.print()
                    console.print("[bold]Authentication Configuration:[/bold]")
                    auth_config = db_client.get_auth_config()

                    if auth_config:
                        # Check email provider
                        email_enabled = auth_config.get("external_email_enabled", False)
                        if email_enabled:
                            display_success("Email provider: enabled")
                        else:
                            display_warning("Email provider: disabled")
                            deployment_issues.append("Email auth not enabled")

                        # Check Site URL (needed for email auth)
                        site_url = auth_config.get("site_url", "")
                        if site_url:
                            display_success(f"Site URL configured: {site_url}")
                        else:
                            display_warning("Site URL not configured")

                        # Check OAuth providers
                        providers_checked = []

                        # Google
                        google_enabled = auth_config.get(
                            "external_google_enabled", False
                        )
                        if google_enabled:
                            display_success("Google OAuth: enabled")
                            google_client_id = auth_config.get(
                                "external_google_client_id", ""
                            )
                            if google_client_id:
                                display_info(f"  Client ID: {google_client_id[:30]}...")
                        else:
                            display_info("Google OAuth: not configured")
                        providers_checked.append("google")

                        # GitHub
                        github_enabled = auth_config.get(
                            "external_github_enabled", False
                        )
                        if github_enabled:
                            display_success("GitHub OAuth: enabled")
                        else:
                            display_info("GitHub OAuth: not configured")
                        providers_checked.append("github")

                        # Check redirect URLs (only warn if OAuth providers are enabled)
                        redirect_urls = auth_config.get("uri_allow_list", "")

                        # Check if any OAuth providers are enabled
                        has_oauth = any(
                            [
                                auth_config.get("external_google_enabled", False),
                                auth_config.get("external_github_enabled", False),
                                auth_config.get("external_azure_enabled", False),
                                auth_config.get("external_apple_enabled", False),
                            ]
                        )

                        if redirect_urls:
                            urls_list = redirect_urls.split(",")
                            has_localhost = any(
                                "localhost" in url or "127.0.0.1" in url
                                for url in urls_list
                            )
                            has_callback = any(
                                "/auth/callback" in url for url in urls_list
                            )

                            if has_localhost:
                                display_success("Local redirect URL configured")
                            else:
                                display_warning(
                                    "Local redirect URL (localhost) not found"
                                )

                            if has_callback:
                                display_success(
                                    f"Callback URLs configured ({len(urls_list)} total)"
                                )
                            else:
                                display_warning("No /auth/callback URLs found")
                        else:
                            if has_oauth:
                                display_warning(
                                    "No redirect URLs configured (needed for OAuth)"
                                )
                                deployment_issues.append(
                                    "Auth redirect URLs not configured for OAuth"
                                )
                            else:
                                display_info(
                                    "No redirect URLs (not needed for email-only auth)"
                                )
                    else:
                        display_warning("Could not fetch auth configuration")
                        display_info(
                            "Ensure access token is configured (run 'dh setup')"
                        )

                else:
                    display_error("Database connection failed")
                    local_issues.append("Cannot connect to database")
            except Exception as e:
                display_error(f"Database connection error: {e}")
                local_issues.append("Database connection error")
        else:
            display_warning("Secret key not configured")
            local_issues.append("Database credentials incomplete")
    else:
        display_warning("Database not configured - run 'dh setup'")
        local_issues.append("Database not configured")

    console.print()

    # Local summary
    if local_issues:
        console.print(
            f"[bold yellow]⚠️  Local environment has {len(local_issues)} issue(s)[/bold yellow]"
        )
        console.print("[bold]Run 'dh setup' to fix configuration issues[/bold]\n")

    # ============================================
    # PART 2: DEPLOYMENT VALIDATION
    # ============================================
    # Only check deployment if .env exists
    if not env_file_exists:
        console.print(
            "[bold yellow]⚠️  Skipping deployment checks (no .env file)[/bold yellow]"
        )
        console.print("[bold]Run 'dh setup' first to configure environment[/bold]\n")
        _print_summary(local_issues, [])
        if local_issues:
            raise typer.Exit(1)
        return

    console.print("[bold cyan]═══ Deployment Configuration ═══[/bold cyan]\n")

    # Load environment variables
    env_vars = _load_env_vars(ctx.frontend_path / ".env")

    # Step 1: Check Backend API (Railway)
    console.print("[bold]Backend API:[/bold]")
    backend_url = env_vars.get("NEXT_PUBLIC_API_URL")

    if not backend_url:
        display_warning("Backend API URL not configured in .env")
        deployment_issues.append("Backend API URL missing")
    elif "localhost" in backend_url or "127.0.0.1" in backend_url:
        display_warning(f"Backend URL is localhost: {backend_url}")
        display_warning("Not deployed yet (using local development)")
    else:
        display_success(f"Backend URL: {backend_url}")

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
                        display_success("✓ Backend is live and responding")
                    else:
                        display_success("✓ Backend is accessible")
                except json.JSONDecodeError:
                    display_success("✓ Backend is accessible")
            else:
                display_error("Backend API is not accessible")
                deployment_issues.append("Backend API not accessible")
        except subprocess.TimeoutExpired:
            display_error("Backend API request timed out")
            deployment_issues.append("Backend API timeout")
        except Exception as e:
            display_warning(f"Could not check backend: {e}")

    console.print()

    # Step 2: Check Supabase
    console.print("[bold]Supabase:[/bold]")
    supabase_url = env_vars.get("NEXT_PUBLIC_SUPABASE_URL")
    supabase_key = env_vars.get("NEXT_PUBLIC_SUPABASE_KEY")

    if not supabase_url:
        display_warning("Supabase URL not configured")
        deployment_issues.append("Supabase URL missing")
    else:
        display_success(f"Supabase URL: {supabase_url}")

        # Check if URL is valid format
        if (
            not supabase_url.startswith("https://")
            or ".supabase.co" not in supabase_url
        ):
            display_warning("Supabase URL format looks incorrect")
            deployment_issues.append("Supabase URL format invalid")

    if not supabase_key:
        display_warning("Supabase anon key not configured")
        deployment_issues.append("Supabase anon key missing")
    else:
        display_success("Supabase anon key configured")

    console.print()

    # Step 3: Check Frontend Deployment
    console.print("[bold]Frontend Deployment:[/bold]")

    # Try to find a production URL
    frontend_url = env_vars.get("NEXT_PUBLIC_VERCEL_URL") or env_vars.get("VERCEL_URL")

    if frontend_url:
        # Ensure it starts with https://
        if not frontend_url.startswith("http"):
            frontend_url = f"https://{frontend_url}"

        display_success(f"Frontend URL: {frontend_url}")

        # Try to access the frontend
        try:
            result = subprocess.run(
                ["curl", "-s", "-f", "-m", "10", "-I", frontend_url],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                display_success("✓ Frontend is live on Vercel")
            else:
                display_warning("Frontend URL not accessible")
                deployment_issues.append("Frontend not deployed or not accessible")
        except subprocess.TimeoutExpired:
            display_warning("Frontend request timed out")
        except Exception as e:
            display_warning(f"Could not check frontend: {e}")
    else:
        display_warning("Frontend URL not found in .env")
        display_warning("Add VERCEL_URL to .env after deploying to Vercel")
        display_warning("Or check manually at your Vercel deployment URL")

    console.print()

    # Final summary
    _print_summary(local_issues, deployment_issues)

    if local_issues or deployment_issues:
        raise typer.Exit(1)


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


def _print_summary(local_issues: list, deployment_issues: list):
    """Print validation summary."""
    console.print("[bold cyan]═══ Summary ═══[/bold cyan]\n")

    total_issues = len(local_issues) + len(deployment_issues)

    if not local_issues and not deployment_issues:
        console.print("✨ [bold green]All checks passed![/bold green]")
        console.print(
            "\n[bold]Your environment is ready for development and deployment[/bold]"
        )
        return

    if local_issues:
        console.print(
            f"[bold red]❌ Local Environment: {len(local_issues)} issue(s)[/bold red]"
        )
        for issue in local_issues:
            console.print(f"  • {issue}")
        console.print()

    if deployment_issues:
        console.print(
            f"[bold yellow]⚠️  Deployment: {len(deployment_issues)} issue(s)[/bold yellow]"
        )
        for issue in deployment_issues:
            console.print(f"  • {issue}")
        console.print()

    console.print(f"[bold]Total: {total_issues} issue(s) found[/bold]\n")

    if local_issues:
        console.print("[bold]Fix local issues:[/bold]")
        console.print("  Run: [cyan]dh setup[/cyan]\n")

    if deployment_issues:
        console.print("[bold]Fix deployment issues:[/bold]")
        console.print(
            "  See: [cyan]https://github.com/dskarbrevik/devhand/blob/main/DEPLOYMENT_GUIDE.md[/cyan]\n"
        )
