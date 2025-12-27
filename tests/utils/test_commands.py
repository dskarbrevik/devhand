"""Tests for command execution utilities."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from dh.utils.commands import (
    check_command_exists,
    run_command,
    get_command_output,
    check_tool_version,
)


class TestCheckCommandExists:
    """Test suite for checking command existence."""

    def test_check_existing_command(self):
        """Test that existing commands are detected."""
        # These commands should exist on most systems
        assert check_command_exists("ls") is True
        assert check_command_exists("echo") is True

    def test_check_nonexistent_command(self):
        """Test that non-existent commands return False."""
        assert check_command_exists("nonexistent_command_12345") is False


class TestRunCommand:
    """Test suite for running commands."""

    @patch("dh.utils.commands.subprocess.run")
    def test_run_command_string(self, mock_run):
        """Test running a command as a string."""
        mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")

        result = run_command("echo test")

        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[1]["shell"] is True
        assert result.returncode == 0

    @patch("dh.utils.commands.subprocess.run")
    def test_run_command_list(self, mock_run):
        """Test running a command as a list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")

        run_command(["echo", "test"])

        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[1]["shell"] is False

    @patch("dh.utils.commands.subprocess.run")
    def test_run_command_with_cwd(self, mock_run, tmp_path: Path):
        """Test running command with working directory."""
        mock_run.return_value = MagicMock(returncode=0)

        run_command("pwd", cwd=tmp_path)

        args = mock_run.call_args
        assert args[1]["cwd"] == tmp_path

    @patch("dh.utils.commands.subprocess.run")
    def test_run_command_capture_output(self, mock_run):
        """Test capturing command output."""
        mock_run.return_value = MagicMock(returncode=0, stdout="test output", stderr="")

        result = run_command("echo test", capture_output=True)

        args = mock_run.call_args
        assert args[1]["capture_output"] is True
        assert result.stdout == "test output"

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


class TestGetCommandOutput:
    """Test suite for getting command output."""

    @patch("dh.utils.commands.subprocess.run")
    def test_get_command_output_success(self, mock_run):
        """Test getting output from successful command."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="version 1.0.0\n", stderr=""
        )

        output = get_command_output(["tool", "--version"])

        assert output == "version 1.0.0"

    @patch("dh.utils.commands.subprocess.run")
    def test_get_command_output_with_cwd(self, mock_run, tmp_path: Path):
        """Test getting output with custom working directory."""
        mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")

        get_command_output(["pwd"], cwd=tmp_path)

        args = mock_run.call_args
        assert args[1]["cwd"] == tmp_path


class TestCheckToolVersion:
    """Test suite for checking tool versions."""

    @patch("dh.utils.commands.get_command_output")
    def test_check_tool_version_success(self, mock_get_output):
        """Test successfully getting tool version."""
        mock_get_output.return_value = "node v20.0.0"

        version = check_tool_version("node", "--version")

        assert version == "node v20.0.0"
        mock_get_output.assert_called_once_with(["node", "--version"])

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
