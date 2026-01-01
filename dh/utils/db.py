"""Database utilities for Supabase operations."""

import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from supabase import Client, create_client

console = Console()

# SQL migration for the schema_migrations table (tracks applied migrations)
SCHEMA_MIGRATIONS_SQL = """\
-- Create the schema_migrations table to track applied migrations
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Grant permissions (service role only - migrations are admin operations)
GRANT ALL ON public.schema_migrations TO service_role;
"""

# SQL migration for the allowed_users table
ALLOWED_USERS_MIGRATION_SQL = """\
-- Create the allowed_users table for beta access control
-- This table is used by the frontend middleware to check if a user is allowed
CREATE TABLE IF NOT EXISTS public.allowed_users (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE public.allowed_users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read their own allowed_users row
-- This allows the frontend middleware to check if a user is allowed
CREATE POLICY "Users can view own allowed status"
    ON public.allowed_users
    FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Service role can manage all rows (for admin operations)
-- Note: Service role bypasses RLS by default, but explicit policy for clarity
CREATE POLICY "Service role can manage allowed_users"
    ON public.allowed_users
    FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- Grant necessary permissions
GRANT SELECT ON public.allowed_users TO authenticated;
GRANT ALL ON public.allowed_users TO service_role;
"""


class DatabaseClient:
    """Wrapper for database operations using Supabase SDK."""

    def __init__(
        self,
        url: str,
        secret_key: str,  # sb_secret_* (new) or service_role JWT (legacy)
        db_password: Optional[str] = None,
        project_ref: Optional[str] = None,
        access_token: Optional[str] = None,  # sbp_* for Management API
    ):
        """Initialize database client.

        Args:
            url: Supabase project URL
            secret_key: Secret API key (sb_secret_* or legacy service_role JWT)
            db_password: Database password (not used with SDK approach)
            project_ref: Project reference ID (extracted from URL if not provided)
            access_token: Supabase access token for Management API (sbp_*)
        """
        self.url = url
        self.secret_key = secret_key
        self.db_password = db_password
        self.access_token = access_token

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

        Returns True if inserted, False if already exists or error.
        """
        try:
            self.client.table("allowed_users").insert({"user_id": user_id}).execute()
            return True
        except Exception as e:
            # Check if it's a duplicate key error
            error_str = str(e).lower()
            if (
                "duplicate" in error_str
                or "already exists" in error_str
                or "unique" in error_str
            ):
                return False  # Already exists
            console.print(f"Error inserting user: {e}", style="yellow")
            return False

    def check_user_allowed(self, user_id: str) -> bool:
        """Check if a user is in the allowed_users table.

        Returns True if user is allowed, False otherwise.
        """
        try:
            result = (
                self.client.table("allowed_users")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            return len(result.data) > 0
        except Exception as e:
            console.print(f"Error checking user: {e}", style="yellow")
            return False

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists by trying to query it.

        Returns True if table exists, False otherwise.
        """
        try:
            result = self.client.table(table_name).select("*").limit(1).execute()
            # If we can query it and get a result object with data attribute, table exists
            return hasattr(result, "data")
        except Exception as e:
            # Check if it's a "relation does not exist" type error
            error_msg = str(e).lower()
            if (
                "does not exist" in error_msg
                or "not found" in error_msg
                or "relation" in error_msg
            ):
                return False
            # For other errors, we can't determine - assume it doesn't exist
            console.print(f"Could not verify table {table_name}: {e}", style="dim")
            return False

    def ensure_schema_migrations_table(self) -> bool:
        """Ensure the schema_migrations table exists for tracking migrations.

        This table is required before running any migrations.
        Returns True if table exists or was created successfully.
        """
        if self.table_exists("schema_migrations"):
            return True

        console.print("📝 Creating schema_migrations table...", style="blue")
        success = self._execute_sql(SCHEMA_MIGRATIONS_SQL)

        if success:
            console.print("✅ schema_migrations table created", style="green")
        else:
            console.print("❌ Failed to create schema_migrations table", style="red")

        return success

    def ensure_database_tables(self, migrations_dir: Optional[Path] = None) -> bool:
        """Ensure all required database tables exist.

        Creates schema_migrations and allowed_users tables if they don't exist.
        This is typically called during 'dh setup'.

        Args:
            migrations_dir: Optional path to save migration files for version control

        Returns True if all tables exist or were created successfully.
        """
        console.print("🗄️  Checking database tables...", style="blue")

        # First ensure schema_migrations exists (needed for tracking)
        if not self.ensure_schema_migrations_table():
            return False

        # Then ensure allowed_users exists
        if not self.ensure_allowed_users_table(migrations_dir):
            return False

        console.print("✅ All required database tables are ready", style="green")
        return True

    def ensure_allowed_users_table(self, migrations_dir: Optional[Path] = None) -> bool:
        """Ensure the allowed_users table exists with proper RLS policies.

        If migrations_dir is provided, writes the migration file there for version control.
        The migration is tracked in schema_migrations table to prevent re-running.

        Args:
            migrations_dir: Optional path to migrations directory to save the SQL file

        Returns True if table exists or was created successfully.
        """
        # Check if table already exists
        if self.table_exists("allowed_users"):
            console.print("✅ allowed_users table exists", style="green")
            return True

        console.print("📝 Creating allowed_users table...", style="blue")

        # If migrations_dir provided, write migration file and use run_migrations
        if migrations_dir:
            migration_file = self._write_allowed_users_migration(migrations_dir)
            if migration_file:
                # Run migrations (handles schema_migrations tracking)
                return self.run_migrations(migrations_dir)
            else:
                console.print(
                    "⚠️  Could not write migration file, executing directly",
                    style="yellow",
                )

        # Execute directly (fallback if no migrations_dir)
        success = self._execute_sql(ALLOWED_USERS_MIGRATION_SQL)

        if success:
            console.print(
                "✅ allowed_users table created with RLS policies", style="green"
            )
        else:
            console.print("❌ Failed to create allowed_users table", style="red")

        return success

    def _write_allowed_users_migration(self, migrations_dir: Path) -> Optional[Path]:
        """Write the allowed_users migration file if it doesn't exist.

        Returns the path to the migration file, or None if it couldn't be written.
        """
        # Check if migration already exists (any file with 'allowed_users' in name)
        existing = list(migrations_dir.glob("*_create_allowed_users.sql"))
        if existing:
            console.print(
                f"✅ Migration file already exists: {existing[0].name}", style="green"
            )
            return existing[0]

        # Create migrations directory if needed
        migrations_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_create_allowed_users.sql"
        migration_path = migrations_dir / filename

        try:
            migration_path.write_text(ALLOWED_USERS_MIGRATION_SQL)
            console.print(f"📄 Created migration: {filename}", style="blue")
            return migration_path
        except Exception as e:
            console.print(f"❌ Failed to write migration file: {e}", style="red")
            return None

    def sync_allowed_users(
        self,
        emails: list[str],
        ensure_table: bool = True,
        migrations_dir: Optional[Path] = None,
    ) -> dict[str, int]:
        """Sync a list of emails to the allowed_users table.

        Args:
            emails: List of email addresses to sync
            ensure_table: If True, create table if it doesn't exist
            migrations_dir: Optional path to save migration file for version control

        Returns dict with counts: {'added': n, 'skipped': n, 'not_found': n}
        """
        # Ensure table exists before syncing
        if ensure_table:
            if not self.ensure_allowed_users_table(migrations_dir):
                console.print(
                    "❌ Cannot sync users - table creation failed", style="red"
                )
                return {"added": 0, "skipped": 0, "not_found": 0}

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

            # Check if user is already in allowed_users
            if self.check_user_allowed(user["id"]):
                console.print(
                    f"⏭️  {email} already in allowed_users",
                    style="dim",
                )
                stats["skipped"] += 1
                continue

            # Insert into allowed_users
            if self.insert_allowed_user(user["id"]):
                console.print(f"✅ Added {email} to allowed_users", style="green")
                stats["added"] += 1
            else:
                console.print(
                    f"⚠️  Failed to add {email} (may already exist or error occurred)",
                    style="yellow",
                )
                stats["skipped"] += 1

        return stats

    def run_migration_file(self, migration_path: Path) -> bool:
        """Run a SQL migration file using Supabase Python SDK.

        Executes SQL directly through Supabase's API.
        """
        if not migration_path.exists():
            console.print(f"❌ Migration file not found: {migration_path}", style="red")
            return False

        # Read migration file
        with open(migration_path) as f:
            sql_content = f.read()

        console.print(f"\n📝 Processing migration: {migration_path.name}", style="blue")

        # Execute SQL using Supabase REST API
        try:
            success = self._execute_sql(sql_content)
            if success:
                console.print(
                    f"✅ Migration executed: {migration_path.name}", style="green"
                )
                return True
            else:
                console.print(
                    f"❌ Migration failed: {migration_path.name}", style="red"
                )
                return False
        except Exception as e:
            console.print(f"❌ Error executing migration: {e}", style="red")
            return False

    def _execute_sql(self, sql: str) -> bool:
        """Execute raw SQL using Supabase's PostgreSQL connection via RPC.

        Uses the postgrest query endpoint to execute SQL.
        """
        if not self.project_ref:
            console.print("❌ Project reference not found", style="red")
            return False

        try:
            # Use Supabase's query endpoint for SQL execution
            # This requires the service_role key or secret key with appropriate permissions

            # Try direct SQL execution via PostgREST
            # Note: This may not work for DDL statements in some Supabase configurations
            # In that case, we'll use the Management API

            # Split SQL into individual statements
            statements = [s.strip() for s in sql.split(";") if s.strip()]

            for statement in statements:
                if not statement:
                    continue

                # Use the Management API for DDL operations
                # Format: POST https://api.supabase.com/v1/projects/{ref}/database/query
                mgmt_url = f"https://api.supabase.com/v1/projects/{self.project_ref}/database/query"

                # Use access_token if available, otherwise fall back to secret_key
                auth_token = self.access_token if self.access_token else self.secret_key
                mgmt_headers = {
                    "Authorization": f"Bearer {auth_token}",
                    "Content-Type": "application/json",
                }

                payload = {"query": statement}

                console.print(f"  Executing: {statement[:60]}...", style="dim")
                response = requests.post(
                    mgmt_url, headers=mgmt_headers, json=payload, timeout=30
                )

                if response.status_code in [200, 201]:
                    console.print("  ✓ Statement executed", style="green")
                else:
                    # If Management API fails, try direct execution
                    console.print(
                        f"  ⚠️  Management API returned {response.status_code}, trying alternate method",
                        style="yellow",
                    )

                    # Try using the client's query method
                    try:
                        # Execute via the client directly
                        # This uses PostgREST which may not support all DDL
                        self.client.postgrest.rpc(
                            "exec", {"query": statement}
                        ).execute()
                        console.print("  ✓ Statement executed via RPC", style="green")
                    except Exception as rpc_error:
                        console.print(
                            f"  ❌ Failed: {response.text if response.status_code != 200 else str(rpc_error)}",
                            style="red",
                        )
                        return False

            return True

        except requests.exceptions.RequestException as e:
            console.print(f"❌ Network error: {e}", style="red")
            return False
        except Exception as e:
            console.print(f"❌ Execution error: {e}", style="red")
            return False

    def run_migrations(self, migrations_dir: Path) -> bool:
        """Run all SQL migration files in a directory.

        Executes in alphabetical order (timestamped filenames ensure correct order).
        Tracks applied migrations in schema_migrations table.
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

        # Get list of already applied migrations
        applied_migrations = self._get_applied_migrations()

        # Filter out already applied migrations
        pending_migrations = [f for f in sql_files if f.stem not in applied_migrations]

        if not pending_migrations:
            console.print("✅ All migrations already applied", style="green")
            return True

        console.print(
            f"{len(pending_migrations)} pending migration(s) to apply", style="blue"
        )

        success = True
        for sql_file in pending_migrations:
            if not self.run_migration_file(sql_file):
                success = False
                break

            # Record migration as applied
            if not self._record_migration(sql_file.stem):
                console.print(
                    f"⚠️  Failed to record migration: {sql_file.stem}", style="yellow"
                )

        return success

    def _get_applied_migrations(self) -> set:
        """Get list of already applied migration versions."""
        try:
            # Check if schema_migrations table exists
            result = self.client.table("schema_migrations").select("version").execute()
            return {row["version"] for row in result.data}
        except Exception:
            # Table doesn't exist yet (first migration)
            console.print(
                "[dim]schema_migrations table not found (will be created)[/dim]"
            )
            return set()

    def _record_migration(self, version: str) -> bool:
        """Record a migration as applied."""
        try:
            self.client.table("schema_migrations").insert(
                {"version": version}
            ).execute()
            return True
        except Exception as e:
            console.print(f"Error recording migration: {e}", style="yellow")
            return False

    def get_auth_config(self) -> Optional[dict]:
        """Get authentication configuration from Supabase Management API.

        Returns dict with auth provider configuration or None on error.
        """
        if not self.access_token:
            console.print(
                "⚠️  Access token not configured (needed for Management API)",
                style="yellow",
            )
            return None

        if not self.project_ref:
            console.print("⚠️  Project reference not found", style="yellow")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Call Supabase Management API
            api_url = (
                f"https://api.supabase.com/v1/projects/{self.project_ref}/config/auth"
            )
            response = requests.get(api_url, headers=headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                console.print("❌ Unauthorized - check your access token", style="red")
                console.print(
                    "   Get a new token: https://supabase.com/dashboard/account/tokens",
                    style="dim",
                )
                return None
            elif response.status_code == 404:
                console.print(
                    "❌ Project not found - check your project reference", style="red"
                )
                return None
            else:
                console.print(f"❌ API error: {response.status_code}", style="red")
                return None

        except requests.exceptions.RequestException as e:
            console.print(f"❌ Failed to fetch auth config: {e}", style="red")
            return None
        except Exception as e:
            console.print(f"❌ Unexpected error: {e}", style="red")
            return None


def create_db_client(
    url: str,
    secret_key: str,  # sb_secret_* (new) or service_role JWT (legacy)
    db_password: Optional[str] = None,
    project_ref: Optional[str] = None,
    access_token: Optional[str] = None,  # sbp_* for Management API
) -> DatabaseClient:
    """Create a database client instance.

    Args:
        url: Supabase project URL
        secret_key: Secret API key (sb_secret_* or legacy service_role JWT)
        db_password: Database password for direct PostgreSQL access
        project_ref: Project reference ID
        access_token: Supabase access token for Management API (sbp_*)

    Returns:
        DatabaseClient instance
    """
    return DatabaseClient(url, secret_key, db_password, project_ref, access_token)
