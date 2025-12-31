"""Tests for database commands."""

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
