"""Tests for make commands."""

from unittest.mock import patch

import pytest
import typer

from dh.commands import make


class TestMakeRequirementsCommand:
    """Test suite for the make requirements command."""

    def test_make_requirements_success(self, mock_context, mock_run_command):
        """Test generating requirements.txt successfully."""
        mock_context.is_backend = True
        mock_context.is_frontend = False

        with patch("dh.commands.make.check_command_exists", return_value=True):
            # Run make requirements command
            make.requirements()

            # Verify uv export was called with correct arguments
            mock_run_command.assert_called_once()
            call_args = mock_run_command.call_args
            assert "uv export" in call_args[0][0]
            assert "--no-dev" in call_args[0][0]
            assert "--no-hashes" in call_args[0][0]
            assert "--output-file requirements.txt" in call_args[0][0]
            assert call_args[1]["cwd"] == mock_context.backend_path

    def test_make_requirements_no_backend(self, mock_context, mock_run_command):
        """Test make requirements fails when no backend project exists."""
        mock_context.is_backend = False
        mock_context.has_backend = False

        with patch("dh.commands.make.check_command_exists", return_value=True):
            # Should raise Exit due to no backend
            with pytest.raises(typer.Exit) as exc_info:
                make.requirements()

            assert exc_info.value.exit_code == 1
            mock_run_command.assert_not_called()

    def test_make_requirements_uv_not_installed(self, mock_context):
        """Test make requirements fails gracefully when uv is not installed."""
        mock_context.is_backend = True

        with patch("dh.commands.make.check_command_exists", return_value=False):
            # Should raise Exit due to missing uv
            with pytest.raises(typer.Exit) as exc_info:
                make.requirements()

            assert exc_info.value.exit_code == 1
