"""Tests for command execution utilities."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from dh.utils.commands import (
    run_command,
    check_tool_version,
)


class TestRunCommand:
    """Test suite for running commands."""

    @patch("dh.utils.commands.subprocess.run")
    def test_run_command_error_handling(self, mock_run):
        """Test that failed commands raise exceptions when check=True."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "bad_command")

        with pytest.raises(subprocess.CalledProcessError):
            run_command("bad_command", check=True)

    @patch("dh.utils.commands.subprocess.run")
    def test_run_command_no_check(self, mock_run):
        """Test that failed commands don't raise when check=False."""
        mock_run.return_value = MagicMock(returncode=1)

        result = run_command("bad_command", check=False)

        assert result.returncode == 1


class TestCheckToolVersion:
    """Test suite for checking tool versions."""

    @patch("dh.utils.commands.check_command_exists")
    def test_check_tool_version_failure(self, mock_check):
        """Test handling tool version check failure when command doesn't exist."""
        mock_check.return_value = False

        version = check_tool_version("nonexistent", "--version")

        assert version is None

    @patch("dh.utils.commands.get_command_output")
    @patch("dh.utils.commands.check_command_exists")
    def test_check_tool_version_called_process_error(self, mock_check, mock_get_output):
        """Test handling CalledProcessError returns 'installed'."""
        mock_check.return_value = True
        mock_get_output.side_effect = subprocess.CalledProcessError(1, "tool")

        version = check_tool_version("tool", "--version")

        assert version == "installed"
