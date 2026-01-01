"""Tests for database commands."""

from pathlib import Path

import pytest
import typer
from unittest.mock import patch

from dh.commands import db


class TestDBMigrateCommand:
    """Test suite for the db migrate command."""

    def test_db_migrate_with_frontend_migrations(
        self, mock_context, mock_db_client, mock_run_command
    ):
        """Test database migrations with frontend migrations."""
        # Create migrations directory
        migrations_dir = mock_context.frontend_path / "supabase" / "migrations"
        migrations_dir.mkdir(parents=True)

        # Create a sample migration file
        migration_file = migrations_dir / "20231225_init.sql"
        migration_file.write_text("CREATE TABLE test (id INT);")

        # Mock the db connection to succeed
        with patch("dh.commands.db.create_db_client") as mock_create:
            mock_client = mock_db_client
            mock_client.test_connection.return_value = True
            mock_client.run_migrations.return_value = True
            mock_create.return_value = mock_client

            # Run db migrate - should attempt to apply migrations
            try:
                db.migrate()
            except typer.Exit:
                # May exit after attempting migrations
                pass

            # Verify that database client was created
            assert mock_create.called

    def test_db_migrate_no_migrations(self, mock_context, mock_db_client):
        """Test db migrate when no migrations directory exists."""
        # Run db migrate without migrations should fail
        with pytest.raises(typer.Exit) as exc_info:
            db.migrate()

        # Verify it exits with error code
        assert exc_info.value.exit_code == 1

    def test_db_migrate_no_config(self, mock_context, monkeypatch):
        """Test db migrate fails without database configuration."""
        # Remove database configuration
        mock_context.config.db.url = None
        mock_context.config.db.secret_key = None

        # Should raise Exit
        with pytest.raises(typer.Exit) as exc_info:
            db.migrate()

        assert exc_info.value.exit_code == 1

    def test_db_migrate_with_backend_migrations(
        self, mock_context, mock_db_client, mock_run_command
    ):
        """Test database migrations from backend migrations directory."""
        # Create migrations in backend directory
        migrations_dir = mock_context.backend_path / "migrations"
        migrations_dir.mkdir(parents=True)

        migration_file = migrations_dir / "20231225_init.sql"
        migration_file.write_text("CREATE TABLE test (id INT);")

        with patch("dh.commands.db.create_db_client") as mock_create:
            mock_client = mock_db_client
            mock_client.test_connection.return_value = True
            mock_client.run_migrations.return_value = True
            mock_create.return_value = mock_client

            try:
                db.migrate()
            except typer.Exit:
                pass

            # Verify migrations were found in backend
            assert mock_create.called
            assert mock_client.run_migrations.called


# Tests for sync_users are difficult to write without invoking the actual typer command
# due to the OptionInfo decorator. These would be better done as integration tests.


# Note: migrate, reset, and seed commands don't exist yet
# These tests are placeholders for future functionality


class TestDBStatusCommand:
    """Test suite for the db status command."""

    def test_db_status(self, mock_context, mock_db_client):
        """Test checking database status."""
        # Mock the database client creation
        with patch("dh.commands.db.create_db_client") as mock_create:
            mock_client = mock_db_client
            mock_client.test_connection.return_value = True
            mock_create.return_value = mock_client

            db.status()

            # Verify that we attempted to check the connection
            assert mock_create.called
            assert mock_client.test_connection.called

    def test_db_status_no_url(self, mock_context):
        """Test db status fails without database URL."""
        mock_context.config.db.url = None

        with pytest.raises(typer.Exit) as exc_info:
            db.status()

        assert exc_info.value.exit_code == 1

    def test_db_status_connection_failed(self, mock_context, mock_db_client):
        """Test db status when connection fails."""
        with patch("dh.commands.db.create_db_client") as mock_create:
            mock_client = mock_db_client
            mock_client.test_connection.return_value = False
            mock_create.return_value = mock_client

            with pytest.raises(typer.Exit) as exc_info:
                db.status()

            assert exc_info.value.exit_code == 1


class TestDBSyncUsersFileLocation:
    """Test suite for sync_users default file location logic."""

    def test_sync_users_default_file_frontend(
        self, mock_context, mock_db_client, tmp_path: Path
    ):
        """Test sync_users uses frontend supabase/allowed_users.txt by default."""
        mock_context.has_frontend = True
        fe_dir = tmp_path / "fe_sync"
        fe_dir.mkdir()
        mock_context.frontend_path = fe_dir

        supabase_dir = mock_context.frontend_path / "supabase"
        supabase_dir.mkdir()
        users_file = supabase_dir / "allowed_users.txt"
        users_file.write_text("user@example.com\n")

        with patch("dh.commands.db.get_db_client", return_value=mock_db_client):
            mock_db_client.sync_allowed_users.return_value = {
                "added": 1,
                "skipped": 0,
                "not_found": 0,
            }

            from dh.commands.db import sync_users

            sync_users(file=None)

            # Should use frontend default location
            mock_db_client.sync_allowed_users.assert_called_once()
            call_emails = mock_db_client.sync_allowed_users.call_args[0][0]
            assert len(call_emails) == 1
            assert "user@example.com" in call_emails

    def test_sync_users_default_file_workspace_root(
        self, mock_context, mock_db_client, tmp_path: Path
    ):
        """Test sync_users uses workspace root when no frontend."""
        mock_context.has_frontend = False
        mock_context.workspace_root = tmp_path

        users_file = mock_context.workspace_root / "allowed_users.txt"
        users_file.write_text("user@example.com\n")

        with patch("dh.commands.db.get_db_client", return_value=mock_db_client):
            mock_db_client.sync_allowed_users.return_value = {
                "added": 1,
                "skipped": 0,
                "not_found": 0,
            }

            from dh.commands.db import sync_users

            sync_users(file=None)

            # Should use workspace root default location
            mock_db_client.sync_allowed_users.assert_called_once()
            call_emails = mock_db_client.sync_allowed_users.call_args[0][0]
            assert len(call_emails) == 1
            assert "user@example.com" in call_emails


class TestDBMigrateSearchLocations:
    """Test suite for migrate directory search logic."""

    def test_migrate_searches_frontend_migrations(
        self, mock_context, mock_db_client, tmp_path: Path
    ):
        """Test migrate finds migrations in frontend supabase directory."""
        mock_context.has_backend = False
        mock_context.has_frontend = True
        fe_dir = tmp_path / "fe_migrate"
        fe_dir.mkdir()
        mock_context.frontend_path = fe_dir
        mock_context.config.db.password = "test_pass"

        # Create frontend migrations
        fe_migrations = mock_context.frontend_path / "supabase" / "migrations"
        fe_migrations.mkdir(parents=True)
        (fe_migrations / "001_initial.sql").write_text("-- migration")

        with patch("dh.commands.db.get_db_client", return_value=mock_db_client):
            mock_db_client.run_migrations.return_value = True

            from dh.commands.db import migrate

            migrate()

            # Should find and use frontend migrations
            mock_db_client.run_migrations.assert_called_once()
            call_path = mock_db_client.run_migrations.call_args[0][0]
            assert "supabase" in str(call_path)

    def test_migrate_searches_workspace_root(
        self, mock_context, mock_db_client, tmp_path: Path
    ):
        """Test migrate falls back to workspace root migrations."""
        mock_context.has_backend = False
        mock_context.has_frontend = False
        mock_context.workspace_root = tmp_path
        mock_context.config.db.password = "test_pass"

        # Create workspace root migrations
        root_migrations = mock_context.workspace_root / "migrations"
        root_migrations.mkdir()
        (root_migrations / "001_initial.sql").write_text("-- migration")

        with patch("dh.commands.db.get_db_client", return_value=mock_db_client):
            mock_db_client.run_migrations.return_value = True

            from dh.commands.db import migrate

            migrate()

            # Should find and use workspace root migrations
            mock_db_client.run_migrations.assert_called_once()
            call_path = mock_db_client.run_migrations.call_args[0][0]
            assert call_path == root_migrations
