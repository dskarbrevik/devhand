"""Database management commands."""

from pathlib import Path

import typer
from rich.console import Console

from dh.context import get_context
from dh.utils.db import create_db_client
from dh.utils.prompts import display_error, display_info, display_warning

app = typer.Typer(help="Database management commands")
console = Console()


def get_db_client():
    """Get database client from config."""
    ctx = get_context()

    if not ctx.config.db.url or not ctx.config.db.secret_key:
        display_error("Database not configured")
        display_info("Run 'dh setup' to configure database credentials")
        display_info("Note: Database operations require the secret/service_role key")
        raise typer.Exit(1)

    return create_db_client(
        ctx.config.db.url,
        ctx.config.db.secret_key,
        ctx.config.db.password,
        ctx.config.db.project_ref,
        ctx.config.db.access_token,  # Pass access token for Management API
    )


@app.command()
def migrate():
    """Run pending database migrations."""
    console.print("🗄️  Running database migrations...\n")

    ctx = get_context()
    db_client = get_db_client()

    # Find migrations directory
    migrations_dir = None

    # Check backend project for migrations first
    if ctx.has_backend:
        be_migrations = ctx.backend_path / "migrations"
        if be_migrations.exists():
            migrations_dir = be_migrations

    # Check frontend project for migrations (legacy location)
    if not migrations_dir and ctx.has_frontend:
        fe_migrations = ctx.frontend_path / "supabase" / "migrations"
        if fe_migrations.exists():
            migrations_dir = fe_migrations

    # Check workspace root
    if not migrations_dir:
        root_migrations = ctx.workspace_root / "migrations"
        if root_migrations.exists():
            migrations_dir = root_migrations

    if not migrations_dir:
        display_error("No migrations directory found")
        display_info(
            "Expected: [backend]/migrations/ or [frontend]/supabase/migrations/ or [workspace]/migrations/"
        )
        raise typer.Exit(1)

    display_info(f"Using migrations from: {migrations_dir}")

    if not ctx.config.db.password:
        display_error("Database password required for migrations")
        display_info("Run 'dh setup' to configure database password")
        raise typer.Exit(1)

    # Run migrations
    if db_client.run_migrations(migrations_dir):
        console.print("\n✅ [bold green]Database setup complete![/bold green]")
    else:
        display_error("Database setup failed")
        raise typer.Exit(1)


@app.command()
def sync_users(
    file: str = typer.Option(
        None,
        "--file",
        "-f",
        help="Path to file containing emails (one per line)",
    ),
):
    """Sync allowed users from file to database."""
    console.print("🔄 Syncing allowed users...\n")

    ctx = get_context()
    db_client = get_db_client()

    # Determine file path
    if file:
        users_file = Path(file)
    else:
        # Default locations
        if ctx.has_frontend:
            users_file = ctx.frontend_path / "supabase" / "allowed_users.txt"
        else:
            users_file = ctx.workspace_root / "allowed_users.txt"

    if not users_file.exists():
        display_error(f"File not found: {users_file}")
        display_info("Specify file with --file option or create allowed_users.txt")
        raise typer.Exit(1)

    # Determine migrations directory for saving the migration file
    migrations_dir = None
    if ctx.has_backend:
        migrations_dir = ctx.backend_path / "migrations"
    elif ctx.has_frontend:
        migrations_dir = ctx.frontend_path / "supabase" / "migrations"

    # Read emails
    with open(users_file) as f:
        emails = [
            line.strip() for line in f if line.strip() and not line.startswith("#")
        ]

    if not emails:
        display_warning("No emails found in file")
        return

    display_info(f"Found {len(emails)} email(s) to sync\n")

    # Sync users (will create migration file if table doesn't exist)
    stats = db_client.sync_allowed_users(emails, migrations_dir=migrations_dir)

    # Display summary
    console.print()
    console.print(f"✅ [bold]Added:[/bold] {stats['added']}")
    console.print(f"⚠️  [bold]Already exists/skipped:[/bold] {stats['skipped']}")
    console.print(f"❌ [bold]Not found (need to sign up):[/bold] {stats['not_found']}")
    console.print()

    if stats["not_found"] > 0:
        display_info("Users must sign up before they can be added to allowed list")


@app.command()
def status():
    """Check database connection status."""
    console.print("🔍 Checking database connection...\n")

    ctx = get_context()

    # Display configuration
    if ctx.config.db.url:
        display_info(f"Database URL: {ctx.config.db.url}")
    else:
        display_error("Database URL not configured")
        raise typer.Exit(1)

    if ctx.config.db.project_ref:
        display_info(f"Project ref: {ctx.config.db.project_ref}")

    # Test connection
    db_client = get_db_client()

    if db_client.test_connection():
        console.print("\n✅ [bold green]Database connection successful![/bold green]")
    else:
        console.print("\n❌ [bold red]Database connection failed[/bold red]")
        display_info("Check your credentials in .dh.local.toml")
        raise typer.Exit(1)
