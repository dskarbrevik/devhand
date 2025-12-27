"""Tests for project context."""

from pathlib import Path
from unittest.mock import patch


from dh.context import ProjectContext


class TestProjectContext:
    """Test suite for ProjectContext class."""

    def test_context_initialization_with_frontend_only(self, tmp_path: Path):
        """Test context initialization with only frontend project."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        # Create frontend project
        frontend = workspace / "fe"
        frontend.mkdir()
        (frontend / "package.json").write_text('{"name": "fe"}')
        (frontend / "next.config.ts").write_text("export default {}")

        with patch("dh.context.load_config") as mock_config:
            mock_config.return_value.project.frontend_path = None
            mock_config.return_value.project.backend_path = None
            mock_config.return_value.db.url = None
            mock_config.return_value.db.service_role_key = None

            context = ProjectContext(start_path=frontend)

            assert context.frontend_path == frontend
            assert context.backend_path is None
            assert context.is_frontend is True
            assert context.is_backend is False
            assert context.has_frontend is True
            assert context.has_backend is False

    def test_context_initialization_with_backend_only(self, tmp_path: Path):
        """Test context initialization with only backend project."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        # Create backend project
        backend = workspace / "be"
        backend.mkdir()
        (backend / "pyproject.toml").write_text('[project]\nname = "be"')
        (backend / "main.py").write_text("# app")

        with patch("dh.context.load_config") as mock_config:
            mock_config.return_value.project.frontend_path = None
            mock_config.return_value.project.backend_path = None
            mock_config.return_value.db.url = None
            mock_config.return_value.db.service_role_key = None

            context = ProjectContext(start_path=backend)

            assert context.frontend_path is None
            assert context.backend_path == backend
            assert context.is_frontend is False
            assert context.is_backend is True
            assert context.has_frontend is False
            assert context.has_backend is True

    def test_context_initialization_with_both_projects(self, tmp_path: Path):
        """Test context initialization with both frontend and backend."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        # Create frontend project
        frontend = workspace / "fe"
        frontend.mkdir()
        (frontend / "package.json").write_text('{"name": "fe"}')
        (frontend / "next.config.ts").write_text("export default {}")

        # Create backend project
        backend = workspace / "be"
        backend.mkdir()
        (backend / "pyproject.toml").write_text('[project]\nname = "be"')
        (backend / "main.py").write_text("# app")

        with patch("dh.context.load_config") as mock_config:
            mock_config.return_value.project.frontend_path = None
            mock_config.return_value.project.backend_path = None
            mock_config.return_value.db.url = None
            mock_config.return_value.db.service_role_key = None

            # Start from workspace root
            context = ProjectContext(start_path=workspace)

            assert context.frontend_path == frontend
            assert context.backend_path == backend
            assert context.is_frontend is False
            assert context.is_backend is False
            assert context.has_frontend is True
            assert context.has_backend is True

    def test_context_current_type_detection(self, tmp_path: Path):
        """Test that context correctly detects current directory type."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create frontend project
        frontend = workspace / "frontend"
        frontend.mkdir()
        (frontend / "package.json").write_text('{"name": "fe"}')
        (frontend / "next.config.ts").write_text("export default {}")

        with patch("dh.context.load_config") as mock_config:
            mock_config.return_value.project.frontend_path = None
            mock_config.return_value.project.backend_path = None
            mock_config.return_value.db.url = None
            mock_config.return_value.db.service_role_key = None

            # Initialize from frontend directory
            context = ProjectContext(start_path=frontend)

            assert context.current_type == "frontend"
            assert context.is_frontend is True

    def test_context_with_config_override(self, tmp_path: Path):
        """Test that config overrides auto-detection."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        # Create projects with non-standard names
        frontend = workspace / "custom-fe"
        frontend.mkdir()
        (frontend / "package.json").write_text('{"name": "fe"}')
        (frontend / "next.config.ts").write_text("export default {}")

        backend = workspace / "custom-be"
        backend.mkdir()
        (backend / "pyproject.toml").write_text('[project]\nname = "be"')
        (backend / "main.py").write_text("# app")

        with patch("dh.context.load_config") as mock_config:
            # Create proper config objects using the actual classes
            from dh.utils.config import Config, ProjectConfig, DatabaseConfig

            config = Config(
                project=ProjectConfig(
                    frontend_path="custom-fe", backend_path="custom-be"
                ),
                db=DatabaseConfig(),
            )
            mock_config.return_value = config

            context = ProjectContext(start_path=workspace)

            # Config should override the detection to use custom paths
            assert context.frontend_path == frontend
            assert context.backend_path == backend

    def test_get_target_path_explicit_frontend(self, tmp_path: Path):
        """Test get_target_path with explicit frontend target."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        frontend = workspace / "fe"
        frontend.mkdir()
        (frontend / "package.json").write_text('{"name": "fe"}')
        (frontend / "next.config.ts").write_text("export default {}")

        with patch("dh.context.load_config") as mock_config:
            mock_config.return_value.project.frontend_path = None
            mock_config.return_value.project.backend_path = None
            mock_config.return_value.db.url = None
            mock_config.return_value.db.service_role_key = None

            context = ProjectContext(start_path=workspace)

            result = context.get_target_path("frontend")

            assert result == frontend

    def test_get_target_path_explicit_backend(self, tmp_path: Path):
        """Test get_target_path with explicit backend target."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        backend = workspace / "be"
        backend.mkdir()
        (backend / "pyproject.toml").write_text('[project]\nname = "be"')
        (backend / "main.py").write_text("# app")

        with patch("dh.context.load_config") as mock_config:
            mock_config.return_value.project.frontend_path = None
            mock_config.return_value.project.backend_path = None
            mock_config.return_value.db.url = None
            mock_config.return_value.db.service_role_key = None

            context = ProjectContext(start_path=workspace)

            result = context.get_target_path("backend")

            assert result == backend

    def test_get_target_path_auto_detect(self, tmp_path: Path):
        """Test get_target_path with auto-detection."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        frontend = workspace / "fe"
        frontend.mkdir()
        (frontend / "package.json").write_text('{"name": "fe"}')
        (frontend / "next.config.ts").write_text("export default {}")

        with patch("dh.context.load_config") as mock_config:
            mock_config.return_value.project.frontend_path = None
            mock_config.return_value.project.backend_path = None
            mock_config.return_value.db.url = None
            mock_config.return_value.db.service_role_key = None

            # Start from frontend directory
            context = ProjectContext(start_path=frontend)

            # Auto-detect should return frontend path
            result = context.get_target_path(None)

            assert result == frontend

    def test_get_target_path_no_match(self, tmp_path: Path):
        """Test get_target_path returns None when not in a project."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        frontend = workspace / "fe"
        frontend.mkdir()
        (frontend / "package.json").write_text('{"name": "fe"}')
        (frontend / "next.config.ts").write_text("export default {}")

        with patch("dh.context.load_config") as mock_config:
            mock_config.return_value.project.frontend_path = None
            mock_config.return_value.project.backend_path = None
            mock_config.return_value.db.url = None
            mock_config.return_value.db.service_role_key = None

            # Start from workspace root (not in a project)
            context = ProjectContext(start_path=workspace)

            # Auto-detect should return None
            result = context.get_target_path(None)

            assert result is None

    def test_context_uses_cwd_by_default(self, tmp_path: Path):
        """Test that context uses current directory when no start_path provided."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch("dh.context.load_config") as mock_config:
            mock_config.return_value.project.frontend_path = None
            mock_config.return_value.project.backend_path = None
            mock_config.return_value.db.url = None
            mock_config.return_value.db.service_role_key = None

            # Don't provide start_path, should use Path.cwd()
            context = ProjectContext()

            assert context.start_path.exists()
            assert context.workspace_root.exists()
