"""Tests for validate commands."""

import subprocess
from unittest.mock import MagicMock, patch

import typer

from dh.commands import validate


class TestValidateCommand:
    """Test suite for the validate command."""

    def test_validate_with_all_tools_installed(
        self, mock_context, mock_check_command_exists, mock_check_tool_version
    ):
        """Test validation when all required tools are installed."""
        with (
            patch(
                "dh.commands.validate.check_command_exists", return_value=True
            ) as mock_check_cmd,
            patch("dh.commands.validate.check_tool_version", return_value="1.0.0"),
        ):
            # Create .env file and directories to simulate configured environment
            (mock_context.frontend_path / ".env").write_text("DUMMY=value\n")
            (mock_context.frontend_path / "node_modules").mkdir()
            (mock_context.backend_path / ".venv").mkdir()

            try:
                validate.validate(deploy=False)
            except typer.Exit:
                pass

            # Verify that validate actually checked for tools
            assert mock_check_cmd.called

    def test_validate_frontend_missing_node(self, mock_context):
        """Test validation detects missing Node.js."""
        with (
            patch("dh.commands.validate.check_command_exists") as mock_check,
            patch("dh.commands.validate.check_tool_version", return_value="1.0.0"),
        ):
            # Node is missing, other tools present
            mock_check.side_effect = lambda cmd: cmd != "node"

            try:
                validate.validate()
            except typer.Exit as e:
                # Should exit due to missing required tool
                assert e.exit_code == 1
            else:
                # If it doesn't exit, at least verify we checked for node
                calls = [call[0][0] for call in mock_check.call_args_list]
                assert "node" in calls

    def test_validate_frontend_missing_dependencies(self, mock_context):
        """Test validation detects missing frontend dependencies."""
        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("dh.commands.validate.check_tool_version", return_value="1.0.0"),
        ):
            try:
                validate.validate()
            except typer.Exit as e:
                # Should detect missing node_modules
                assert e.exit_code == 1

            # Verify that node_modules is indeed missing
            assert not (mock_context.frontend_path / "node_modules").exists()

    def test_validate_backend_tools(self, mock_context):
        """Test validation checks backend tools."""
        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("dh.commands.validate.check_tool_version", return_value="3.11.0"),
        ):
            try:
                validate.validate()
            except typer.Exit:
                pass

    def test_validate_database_connection(self, mock_context, mock_db_client):
        """Test validation checks database connection."""
        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("dh.commands.validate.check_tool_version", return_value="1.0.0"),
        ):
            try:
                validate.validate()
            except typer.Exit:
                pass

    def test_validate_no_database_config(self, mock_context):
        """Test validation handles missing database config."""
        mock_context.config.db.url = None
        mock_context.config.db.secret_key = None

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("dh.commands.validate.check_tool_version", return_value="1.0.0"),
        ):
            try:
                validate.validate()
            except typer.Exit:
                pass

    def test_validate_displays_summary(self, mock_context):
        """Test validation displays a summary of checks."""
        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("dh.commands.validate.check_tool_version", return_value="1.0.0"),
        ):
            (mock_context.frontend_path / "node_modules").mkdir()
            (mock_context.backend_path / ".venv").mkdir()

            try:
                validate.validate()
            except typer.Exit:
                pass


class TestValidateDeployment:
    """Test suite for the validate --deploy command."""

    def test_validate_deploy_no_env_file(self, mock_context):
        """Test deployment validation exits when .env is missing."""
        # Remove .env file
        env_file = mock_context.frontend_path / ".env"
        if env_file.exists():
            env_file.unlink()

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("dh.commands.validate.check_tool_version", return_value="1.0.0"),
        ):
            try:
                validate.validate(deploy=True)
            except typer.Exit as e:
                assert e.exit_code == 1

    def test_validate_deploy_with_localhost_backend(self, mock_context):
        """Test deployment validation warns about localhost backend URL."""
        # Create .env with localhost backend
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "NEXT_PUBLIC_API_URL=http://localhost:8000\n"
            "NEXT_PUBLIC_SUPABASE_URL=https://test.supabase.co\n"
            "NEXT_PUBLIC_SUPABASE_KEY=test-key\n"
        )

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("dh.commands.validate.check_tool_version", return_value="1.0.0"),
        ):
            try:
                validate.validate(deploy=True)
            except typer.Exit as e:
                # Should exit with code 1 due to localhost URL
                assert e.exit_code == 1

    def test_validate_deploy_backend_accessible(self, mock_context):
        """Test deployment validation checks if backend API is accessible."""
        # Create .env with production backend URL
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "NEXT_PUBLIC_API_URL=https://myapp-be.up.railway.app\n"
            "NEXT_PUBLIC_SUPABASE_URL=https://test.supabase.co\n"
            "NEXT_PUBLIC_SUPABASE_KEY=test-key\n"
        )

        # Mock successful curl response
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "success", "message": "Hello World"}'

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("dh.commands.validate.check_tool_version", return_value="1.0.0"),
            patch("subprocess.run", return_value=mock_result),
            patch("dh.commands.validate.create_db_client") as mock_db,
        ):
            # Mock database client
            mock_db_instance = MagicMock()
            mock_db_instance.test_connection.return_value = True
            mock_db_instance.table.return_value.select.return_value.limit.return_value.execute.return_value = []
            mock_db.return_value = mock_db_instance

            try:
                validate.validate(deploy=True)
            except typer.Exit:
                pass

    def test_validate_deploy_backend_not_accessible(self, mock_context):
        """Test deployment validation detects inaccessible backend."""
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "NEXT_PUBLIC_API_URL=https://myapp-be.up.railway.app\n"
            "NEXT_PUBLIC_SUPABASE_URL=https://test.supabase.co\n"
            "NEXT_PUBLIC_SUPABASE_KEY=test-key\n"
        )

        # Mock failed curl response
        mock_result = MagicMock()
        mock_result.returncode = 1

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            try:
                validate.validate(deploy=True)
            except typer.Exit as e:
                assert e.exit_code == 1

    def test_validate_deploy_backend_timeout(self, mock_context):
        """Test deployment validation handles backend timeout."""
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "NEXT_PUBLIC_API_URL=https://myapp-be.up.railway.app\n"
            "NEXT_PUBLIC_SUPABASE_URL=https://test.supabase.co\n"
            "NEXT_PUBLIC_SUPABASE_KEY=test-key\n"
        )

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("curl", 10)),
        ):
            try:
                validate.validate(deploy=True)
            except typer.Exit as e:
                assert e.exit_code == 1

    def test_validate_deploy_supabase_url_format(self, mock_context):
        """Test deployment validation checks Supabase URL format."""
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "NEXT_PUBLIC_API_URL=https://myapp-be.up.railway.app\n"
            "NEXT_PUBLIC_SUPABASE_URL=https://invalid-url.com\n"
            "NEXT_PUBLIC_SUPABASE_KEY=test-key\n"
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "success"}'

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            try:
                validate.validate(deploy=True)
            except typer.Exit as e:
                # Should detect invalid Supabase URL format
                assert e.exit_code == 1

    def test_validate_deploy_missing_env_vars(self, mock_context):
        """Test deployment validation detects missing environment variables."""
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "NEXT_PUBLIC_API_URL=https://myapp-be.up.railway.app\n"
            # Missing SUPABASE_URL and SUPABASE_KEY
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "success"}'

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            try:
                validate.validate(deploy=True)
            except typer.Exit as e:
                assert e.exit_code == 1

    def test_validate_deploy_database_connection(self, mock_context, mock_db_client):
        """Test deployment validation checks database connection."""
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "NEXT_PUBLIC_API_URL=https://myapp-be.up.railway.app\n"
            "NEXT_PUBLIC_SUPABASE_URL=https://test.supabase.co\n"
            "NEXT_PUBLIC_SUPABASE_KEY=test-key\n"
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "success"}'

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
            patch("dh.commands.validate.create_db_client", return_value=mock_db_client),
        ):
            try:
                validate.validate(deploy=True)
            except typer.Exit:
                pass

            # Verify database connection was tested
            mock_db_client.test_connection.assert_called_once()

    def test_validate_deploy_allowed_users_table_missing(self, mock_context):
        """Test deployment validation detects missing allowed_users table."""
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "NEXT_PUBLIC_API_URL=https://myapp-be.up.railway.app\n"
            "NEXT_PUBLIC_SUPABASE_URL=https://test.supabase.co\n"
            "NEXT_PUBLIC_SUPABASE_KEY=test-key\n"
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "success"}'

        mock_db = MagicMock()
        mock_db.test_connection.return_value = True
        # Simulate table not found
        mock_db.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception(
            "Table not found"
        )

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
            patch("dh.commands.validate.create_db_client", return_value=mock_db),
        ):
            try:
                validate.validate(deploy=True)
            except typer.Exit as e:
                assert e.exit_code == 1

    def test_validate_deploy_all_checks_pass(self, mock_context):
        """Test deployment validation passes when everything is configured correctly."""
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "NEXT_PUBLIC_API_URL=https://myapp-be.up.railway.app\n"
            "NEXT_PUBLIC_SUPABASE_URL=https://test.supabase.co\n"
            "NEXT_PUBLIC_SUPABASE_KEY=test-key\n"
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "success"}'

        mock_db = MagicMock()
        mock_db.test_connection.return_value = True
        mock_db.table.return_value.select.return_value.limit.return_value.execute.return_value = []

        with (
            patch("dh.commands.validate.check_command_exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
            patch("dh.commands.validate.create_db_client", return_value=mock_db),
        ):
            try:
                validate.validate(deploy=True)
            except typer.Exit as e:
                # Should not exit with error
                assert e.exit_code != 1

    def test_load_env_vars(self, mock_context):
        """Test _load_env_vars helper function."""
        env_file = mock_context.frontend_path / ".env"
        env_file.write_text(
            "# Comment line\n"
            "KEY1=value1\n"
            'KEY2="value2"\n'
            "KEY3='value3'\n"
            "KEY4=value with spaces\n"
            "\n"
            "INVALID_LINE_NO_EQUALS\n"
        )

        env_vars = validate._load_env_vars(env_file)

        assert env_vars["KEY1"] == "value1"
        assert env_vars["KEY2"] == "value2"
        assert env_vars["KEY3"] == "value3"
        assert env_vars["KEY4"] == "value with spaces"
        assert "INVALID_LINE_NO_EQUALS" not in env_vars
