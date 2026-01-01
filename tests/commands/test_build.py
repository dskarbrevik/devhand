"""Tests for build commands."""

from unittest.mock import patch

import pytest
import typer

from dh.commands import build


class TestBuildCommand:
    """Test suite for the build command."""

    def test_build_docker_not_installed(self, mock_context):
        """Test build fails gracefully when Docker is not installed."""
        mock_context.is_frontend = True

        with patch("dh.commands.build.check_command_exists", return_value=False):
            # Run build with docker flag should raise Exit
            with pytest.raises(typer.Exit) as exc_info:
                build.build(docker=True)

            assert exc_info.value.exit_code == 1


class TestRunCommand:
    """Test suite for the run command."""

    def test_run_docker_not_installed(self, mock_context):
        """Test run fails gracefully when Docker is not installed."""
        mock_context.is_frontend = True

        with patch("dh.commands.build.check_command_exists", return_value=False):
            # Run should raise Exit
            with pytest.raises(typer.Exit) as exc_info:
                build.run()

            assert exc_info.value.exit_code == 1


class TestBuildAmbiguousContext:
    """Test suite for build with ambiguous context."""

    def test_build_docker_ambiguous_context_builds_both(self, mock_context):
        """Test docker build with ambiguous context builds both projects."""
        # Ambiguous: not in specific project but both exist
        mock_context.is_frontend = False
        mock_context.is_backend = False
        mock_context.has_frontend = True
        mock_context.has_backend = True

        with (
            patch("dh.commands.build.check_command_exists", return_value=True),
            patch("dh.commands.build.run_command") as mock_run,
        ):
            build.build(docker=True)

            # Should build both images
            assert mock_run.call_count == 2
            calls = [str(call) for call in mock_run.call_args_list]
            assert any("hello-world-fe" in call for call in calls)
            assert any("hello-world-be" in call for call in calls)

    def test_build_regular_ambiguous_context_builds_frontend(self, mock_context):
        """Test regular build with ambiguous context builds frontend only."""
        # Ambiguous: not in specific project but both exist
        mock_context.is_frontend = False
        mock_context.is_backend = False
        mock_context.has_frontend = True
        mock_context.has_backend = True

        with patch("dh.commands.build.run_command") as mock_run:
            build.build(docker=False)

            # Should build frontend (backend has no build step)
            assert mock_run.call_count == 1
            call_str = str(mock_run.call_args_list[0])
            assert "npm run build" in call_str
