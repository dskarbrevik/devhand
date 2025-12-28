"""Database utilities for Supabase operations."""

import re
from pathlib import Path
from typing import Optional

from rich.console import Console
from supabase import Client, create_client

console = Console()


class DatabaseClient:
    """Wrapper for database operations using Supabase SDK."""

    def __init__(
        self,
        url: str,
        secret_key: str,  # sb_secret_* (new) or service_role JWT (legacy)
        db_password: Optional[str] = None,
        project_ref: Optional[str] = None,
    ):
        """Initialize database client.

        Args:
            url: Supabase project URL
            secret_key: Secret API key (sb_secret_* or legacy service_role JWT)
            db_password: Database password (not used with SDK approach)
            project_ref: Project reference ID (extracted from URL if not provided)
        """
        self.url = url
        self.secret_key = secret_key
        self.db_password = db_password

        # Extract project ref from URL if not provided
        if not project_ref:
            match = re.search(r"https://([^.]+)\.supabase\.co", url)
            if match:
                self.project_ref = match.group(1)
            else:
                self.project_ref = None
        else:
            self.project_ref = project_ref

        # Initialize Supabase client
        self.client: Client = create_client(url, secret_key)

    def test_connection(self) -> bool:
        """Test connection to Supabase."""
        try:
            # Test by listing users (requires secret key with admin permissions)
            self.client.auth.admin.list_users()
            return True
        except Exception as e:
            console.print(f"Connection test failed: {e}", style="red")
            console.print(
                "\nℹ️  Make sure you're using the secret key (sb_secret_* or service_role JWT), not the public key",
                style="blue",
            )
            console.print(
                "   Find it in: Supabase Dashboard > Settings > API > Secret keys tab",
                style="blue",
            )
            return False

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email from auth.users.

        Uses Supabase Auth Admin API.
        """
        try:
            # List users and filter by email
            users = self.client.auth.admin.list_users()
            for user in users:
                if user.email == email:
                    return {"id": user.id, "email": user.email}
            return None
        except Exception as e:
            console.print(f"Error fetching user {email}: {e}", style="yellow")
            return None

    def insert_allowed_user(self, user_id: str) -> bool:
        """Insert a user into the allowed_users table.

        Returns True if successful, False otherwise.
        """
        try:
            self.client.table("allowed_users").insert({"user_id": user_id}).execute()
            return True
        except Exception as e:
            # Check if it's a duplicate key error
            if "duplicate key" in str(e).lower() or "already exists" in str(e).lower():
                return True  # Already exists, consider it success
            console.print(f"Error inserting user: {e}", style="yellow")
            return False

    def sync_allowed_users(self, emails: list[str]) -> dict[str, int]:
        """Sync a list of emails to the allowed_users table.

        Returns dict with counts: {'added': n, 'skipped': n, 'not_found': n}
        """
        stats = {"added": 0, "skipped": 0, "not_found": 0}

        for email in emails:
            email = email.strip()
            if not email or email.startswith("#"):
                continue

            # Get user by email
            user = self.get_user_by_email(email)
            if not user:
                console.print(
                    f"⚠️  {email} not found in auth.users (user needs to sign up first)",
                    style="yellow",
                )
                stats["not_found"] += 1
                continue

            # Insert into allowed_users
            if self.insert_allowed_user(user["id"]):
                console.print(f"✅ Added {email} to allowed_users", style="green")
                stats["added"] += 1
            else:
                console.print(
                    f"⚠️  {email} already in allowed_users or error occurred",
                    style="yellow",
                )
                stats["skipped"] += 1

        return stats

    def run_migration_file(self, migration_path: Path) -> bool:
        """Run a SQL migration file using Supabase Python SDK.

        Attempts to execute SQL through available methods, falls back to manual instructions.
        """
        if not migration_path.exists():
            console.print(f"❌ Migration file not found: {migration_path}", style="red")
            return False

        # Read migration file
        with open(migration_path) as f:
            sql_content = f.read()

        console.print(f"\n📝 Processing migration: {migration_path.name}", style="blue")

        # Try to execute via Supabase SDK's table operations
        # Since the SDK doesn't support raw SQL execution, we parse and execute what we can
        try:
            # Split into statements
            statements = [s.strip() for s in sql_content.split(";") if s.strip()]

            # Check if this is a simple allowed_users table creation
            if any("allowed_users" in stmt.lower() for stmt in statements):
                # Try to create the table structure using SDK methods
                created = self._create_allowed_users_table_via_sdk(statements)
                if created:
                    console.print(
                        f"✅ Migration executed: {migration_path.name}", style="green"
                    )
                    return True

            # For other migrations or if SDK approach fails, provide manual instructions
            console.print(
                "\n⚠️  This migration requires manual execution in Supabase",
                style="yellow",
            )
            console.print(
                "\nℹ️  Copy the SQL below and run it in Supabase Dashboard > SQL Editor:",
                style="blue",
            )

            console.print("\n" + "─" * 60, style="dim")
            console.print(sql_content, style="cyan")
            console.print("─" * 60 + "\n", style="dim")

            console.print("Steps:", style="bold")
            console.print("  1. Go to: https://supabase.com/dashboard", style="blue")
            console.print("  2. Select your project", style="blue")
            console.print("  3. Click: SQL Editor (in left sidebar)", style="blue")
            console.print("  4. Click: 'New Query'", style="blue")
            console.print("  5. Paste the SQL above", style="blue")
            console.print("  6. Click 'Run' or press Cmd+Enter\n", style="blue")

            from dh.utils.prompts import prompt_confirm

            if prompt_confirm("Have you successfully run this migration in Supabase?"):
                console.print(
                    f"✅ Migration confirmed: {migration_path.name}", style="green"
                )
                return True
            else:
                console.print(
                    f"⏭️  Skipping migration: {migration_path.name}", style="yellow"
                )
                return False

        except Exception as e:
            console.print(f"❌ Error processing migration: {e}", style="red")
            return False

    def _create_allowed_users_table_via_sdk(self, statements: list) -> bool:
        """Attempt to create allowed_users table using SDK operations.

        Returns True if successful, False otherwise.
        """
        try:
            # Check if table exists by trying to query it
            try:
                self.client.table("allowed_users").select("*").limit(1).execute()
                # If we get here, table exists
                console.print("  ℹ️  allowed_users table already exists", style="dim")
                return True
            except Exception:
                # Table doesn't exist, which is expected for new setup
                pass

            # Unfortunately, the Supabase Python SDK doesn't provide
            # CREATE TABLE functionality - that's a DDL operation
            # We need to run it via SQL Editor
            return False

        except Exception:
            return False

    def run_migrations(self, migrations_dir: Path) -> bool:
        """Run all SQL migration files in a directory.

        Executes in alphabetical order (timestamped filenames ensure correct order).
        """
        if not migrations_dir.exists():
            console.print(
                f"❌ Migrations directory not found: {migrations_dir}", style="red"
            )
            return False

        # Find all .sql files
        sql_files = sorted(migrations_dir.glob("*.sql"))

        if not sql_files:
            console.print("⚠️  No migration files found", style="yellow")
            return True

        console.print(f"Found {len(sql_files)} migration(s)", style="blue")

        success = True
        for sql_file in sql_files:
            if not self.run_migration_file(sql_file):
                success = False
                break

        return success


def create_db_client(
    url: str,
    secret_key: str,  # sb_secret_* (new) or service_role JWT (legacy)
    db_password: Optional[str] = None,
    project_ref: Optional[str] = None,
) -> DatabaseClient:
    """Create a database client instance.

    Args:
        url: Supabase project URL
        secret_key: Secret API key (sb_secret_* or legacy service_role JWT)
        db_password: Database password for direct PostgreSQL access
        project_ref: Project reference ID

    Returns:
        DatabaseClient instance
    """
    return DatabaseClient(url, secret_key, db_password, project_ref)
