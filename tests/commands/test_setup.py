"""Tests for setup commands."""

from unittest.mock import patch, mock_open

import pytest
import typer

from dh.commands import setup


class TestSetupCommand:
    """Test suite for the setup command."""

    def test_setup_detects_projects(
        self, mock_context, mock_check_command_exists, mock_check_tool_version
    ):
        """Test that setup detects frontend and backend projects."""
        with (
            patch("dh.commands.setup.prompt_confirm", return_value=False),
            patch("dh.commands.setup.prompt_text", return_value="test"),
        ):
            # Run setup
            try:
                setup.setup()
            except typer.Exit:
                # Setup exits after user declines DB config
                pass

            # Verify tools were checked
            assert mock_check_command_exists.called

    def test_setup_no_projects_detected(self, mock_context, monkeypatch):
        """Test setup fails when no projects are detected."""
        # Mock context with no projects
        mock_context.has_frontend = False
        mock_context.has_backend = False

        # Should raise Exit
        with pytest.raises(typer.Exit) as exc_info:
            setup.setup()

        assert exc_info.value.exit_code == 1

    def test_setup_missing_tools(self, mock_context, mock_check_command_exists):
        """Test setup warns about missing tools."""
        with (
            patch("dh.commands.setup.check_command_exists") as mock_check,
            patch("dh.commands.setup.prompt_confirm", return_value=False),
        ):
            # Mock some tools missing
            def mock_exists(cmd):
                return cmd in ["node", "npm", "uv"]  # Docker missing

            mock_check.side_effect = mock_exists

            # Run setup - should warn but not fail
            try:
                setup.setup()
            except typer.Exit:
                pass

            assert mock_check.called

    def test_setup_missing_node(self, mock_context):
        """Test setup fails when Node.js is missing for frontend."""
        mock_context.has_frontend = True
        mock_context.has_backend = False

        with (
            patch("dh.commands.setup.check_command_exists") as mock_check,
            patch("dh.commands.setup.check_tool_version", return_value="1.0.0"),
        ):
            # Mock node missing but npm present
            def mock_exists(cmd):
                return cmd != "node"

            mock_check.side_effect = mock_exists

            with pytest.raises(typer.Exit) as exc_info:
                setup.setup()

            assert exc_info.value.exit_code == 1

    def test_setup_with_db_configuration(self, mock_context):
        """Test setup with database configuration."""
        mock_context.has_frontend = True
        mock_context.has_backend = True

        with (
            patch("dh.commands.setup.check_command_exists", return_value=True),
            patch("dh.commands.setup.check_tool_version", return_value="1.0.0"),
            patch("dh.commands.setup.prompt_confirm", return_value=True),
            patch("dh.commands.setup.prompt_text") as mock_prompt,
            patch("dh.commands.setup.save_frontend_env") as mock_save_fe,
            patch("dh.commands.setup.save_backend_env") as mock_save_be,
            patch("dh.commands.setup.run_command"),
            patch("builtins.open", mock_open(read_data=".env\n")),
        ):
            # Mock user inputs
            mock_prompt.side_effect = [
                "https://test.supabase.co",  # db_url
                "test_public_key",  # public_key
                "test_secret_key",  # secret_key
                "test_password",  # db_password
                "test_access_token",  # access_token
                "http://localhost:8000",  # api_url
                "https://test.vercel.app",  # vercel_url
            ]

            try:
                setup.setup()
            except Exception:
                pass

            # Verify env files were saved
            assert mock_save_fe.called
            assert mock_save_be.called

    def test_setup_db_url_extraction(self, mock_context):
        """Test setup extracts project ref from Supabase URL."""
        mock_context.has_frontend = True
        mock_context.has_backend = False

        with (
            patch("dh.commands.setup.check_command_exists", return_value=True),
            patch("dh.commands.setup.check_tool_version", return_value="1.0.0"),
            patch("dh.commands.setup.prompt_confirm", return_value=True),
            patch("dh.commands.setup.prompt_text") as mock_prompt,
            patch("dh.commands.setup.save_frontend_env"),
            patch("dh.commands.setup.run_command"),
            patch("builtins.open", mock_open(read_data=".env\n")),
        ):
            # Mock user inputs with valid Supabase URL
            mock_prompt.side_effect = [
                "https://myproject.supabase.co",
                "test_public_key",
                "test_secret_key",
                "test_password",
                "test_access_token",
                "",  # vercel_url
            ]

            try:
                setup.setup()
            except Exception:
                pass

            # Check that project_ref was extracted
            assert mock_context.config.db.project_ref == "myproject"


class TestInstallCommand:
    """Test suite for the install command."""

    def test_install_frontend_dependencies(self, mock_context, mock_run_command):
        """Test installing frontend dependencies."""
        mock_context.is_frontend = True
        mock_context.is_backend = False

        # Run install
        setup.install()

        # Verify commands were called (npm install + uv sync)
        assert mock_run_command.call_count >= 1

    def test_install_backend_dependencies(self, mock_context, mock_run_command):
        """Test installing backend dependencies."""
        mock_context.is_frontend = False
        mock_context.is_backend = True

        # Run install
        setup.install()

        # Verify commands were called
        assert mock_run_command.call_count >= 1

    def test_install_both_projects(self, mock_context, mock_run_command):
        """Test installing dependencies for both projects."""
        mock_context.is_frontend = False
        mock_context.is_backend = False
        mock_context.has_frontend = True
        mock_context.has_backend = True

        # Run install
        setup.install()

        # Verify both installs were called
        assert mock_run_command.call_count >= 2

        calls = [call[0][0] for call in mock_run_command.call_args_list]
        assert any("npm install" in call for call in calls)
        assert any("uv sync" in call for call in calls)

    def test_install_frontend_failure(self, mock_context):
        """Test install handles frontend failure."""
        mock_context.has_frontend = True
        mock_context.has_backend = False

        with patch(
            "dh.commands.setup.run_command", side_effect=Exception("npm install failed")
        ):
            with pytest.raises(typer.Exit) as exc_info:
                setup.install()

            assert exc_info.value.exit_code == 1

    def test_install_backend_failure(self, mock_context):
        """Test install handles backend failure."""
        mock_context.has_frontend = False
        mock_context.has_backend = True

        with patch(
            "dh.commands.setup.run_command", side_effect=Exception("uv sync failed")
        ):
            with pytest.raises(typer.Exit) as exc_info:
                setup.install()

            assert exc_info.value.exit_code == 1
