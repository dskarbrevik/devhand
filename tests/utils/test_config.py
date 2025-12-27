"""Tests for config utilities."""

from pathlib import Path

from dh.utils.config import Config, DatabaseConfig, load_config, save_frontend_env


class TestLoadConfig:
    """Test suite for loading configuration from .env files."""

    def test_load_config_from_frontend_env(self, tmp_path: Path):
        """Test loading config from frontend .env file."""
        # Create frontend directory structure in a unique location
        test_workspace = tmp_path / "test_workspace"
        test_workspace.mkdir()
        frontend_path = test_workspace / "frontend"
        frontend_path.mkdir()

        # Create .env file with Supabase config
        env_file = frontend_path / ".env"
        env_file.write_text(
            """# Frontend Environment
NEXT_PUBLIC_SUPABASE_URL=https://testproject.supabase.co
NEXT_PUBLIC_SUPABASE_KEY=test_public_key
SUPABASE_SECRET_KEY=test_secret_key
SUPABASE_DB_PASSWORD=test_password
SUPABASE_ACCESS_TOKEN=test_token
"""
        )

        # Load config
        config = load_config(test_workspace, frontend_path=frontend_path)

        # Verify database config loaded correctly
        assert config.db.url == "https://testproject.supabase.co"
        assert config.db.public_key == "test_public_key"
        assert config.db.secret_key == "test_secret_key"
        assert config.db.password == "test_password"
        assert config.db.access_token == "test_token"
        assert config.db.project_ref == "testproject"

    def test_load_config_no_env_files(self, tmp_path: Path):
        """Test loading config when no .env files exist."""
        config = load_config(tmp_path)

        # Should return empty config
        assert config.db.url is None
        assert config.db.secret_key is None

    def test_load_config_partial_env(self, tmp_path: Path):
        """Test loading config with partial .env data."""
        test_workspace = tmp_path / "test_workspace2"
        test_workspace.mkdir()
        frontend_path = test_workspace / "frontend"
        frontend_path.mkdir()

        # Create .env file with only URL
        env_file = frontend_path / ".env"
        env_file.write_text("NEXT_PUBLIC_SUPABASE_URL=https://partial.supabase.co\n")

        config = load_config(test_workspace, frontend_path=frontend_path)

        # Verify only URL is loaded
        assert config.db.url == "https://partial.supabase.co"
        assert config.db.project_ref == "partial"
        assert config.db.secret_key is None

    def test_load_config_with_comments(self, tmp_path: Path):
        """Test that comments are ignored in .env files."""
        test_workspace = tmp_path / "test_workspace3"
        test_workspace.mkdir()
        frontend_path = test_workspace / "frontend"
        frontend_path.mkdir()

        env_file = frontend_path / ".env"
        env_file.write_text(
            """# This is a comment
NEXT_PUBLIC_SUPABASE_URL=https://test.supabase.co
# Another comment
SUPABASE_SECRET_KEY=secret_key
"""
        )

        config = load_config(test_workspace, frontend_path=frontend_path)

        assert config.db.url == "https://test.supabase.co"
        assert config.db.secret_key == "secret_key"

    def test_load_config_with_quotes(self, tmp_path: Path):
        """Test that quotes are stripped from values."""
        test_workspace = tmp_path / "test_workspace4"
        test_workspace.mkdir()
        frontend_path = test_workspace / "frontend"
        frontend_path.mkdir()

        env_file = frontend_path / ".env"
        env_file.write_text(
            """NEXT_PUBLIC_SUPABASE_URL="https://quoted.supabase.co"
SUPABASE_SECRET_KEY='single_quoted_key'
"""
        )

        config = load_config(test_workspace, frontend_path=frontend_path)

        assert config.db.url == "https://quoted.supabase.co"
        assert config.db.secret_key == "single_quoted_key"

    def test_load_config_stores_paths(self, tmp_path: Path):
        """Test that project paths are stored in config."""
        test_workspace = tmp_path / "test_workspace5"
        test_workspace.mkdir()
        frontend_path = test_workspace / "frontend"
        backend_path = test_workspace / "backend"
        frontend_path.mkdir()
        backend_path.mkdir()

        config = load_config(
            test_workspace, frontend_path=frontend_path, backend_path=backend_path
        )

        assert config.project.frontend_path == str(frontend_path)
        assert config.project.backend_path == str(backend_path)


class TestSaveFrontendEnv:
    """Test suite for saving frontend .env files."""

    def test_save_frontend_env_new_file(self, tmp_path: Path):
        """Test saving config to a new .env file."""
        test_workspace = tmp_path / "test_workspace6"
        test_workspace.mkdir()
        frontend_path = test_workspace / "frontend"
        frontend_path.mkdir()

        config = Config(
            db=DatabaseConfig(
                url="https://newproject.supabase.co",
                public_key="new_public_key",
                secret_key="new_secret_key",
                password="new_password",
            )
        )

        save_frontend_env(frontend_path, config, api_url="https://api.example.com")

        # Verify file was created
        env_file = frontend_path / ".env"
        assert env_file.exists()

        # Verify content
        content = env_file.read_text()
        assert "NEXT_PUBLIC_API_URL=https://api.example.com" in content
        assert "NEXT_PUBLIC_SUPABASE_URL=https://newproject.supabase.co" in content
        assert "NEXT_PUBLIC_SUPABASE_KEY=new_public_key" in content
        assert "SUPABASE_SECRET_KEY=new_secret_key" in content
        assert "SUPABASE_DB_PASSWORD=new_password" in content

    def test_save_frontend_env_updates_existing(self, tmp_path: Path):
        """Test updating an existing .env file."""
        test_workspace = tmp_path / "test_workspace7"
        test_workspace.mkdir()
        frontend_path = test_workspace / "frontend"
        frontend_path.mkdir()

        # Create existing .env
        env_file = frontend_path / ".env"
        env_file.write_text("NEXT_PUBLIC_SUPABASE_URL=https://old.supabase.co\n")

        config = Config(
            db=DatabaseConfig(
                url="https://updated.supabase.co",
                public_key="updated_key",
            )
        )

        save_frontend_env(frontend_path, config)

        # Verify file was updated
        content = env_file.read_text()
        assert "NEXT_PUBLIC_SUPABASE_URL=https://updated.supabase.co" in content
        assert "NEXT_PUBLIC_SUPABASE_KEY=updated_key" in content
        assert "old.supabase.co" not in content

    def test_save_frontend_env_preserves_structure(self, tmp_path: Path):
        """Test that saved .env has proper structure with comments."""
        test_workspace = tmp_path / "test_workspace8"
        test_workspace.mkdir()
        frontend_path = test_workspace / "frontend"
        frontend_path.mkdir()

        config = Config(db=DatabaseConfig(url="https://test.supabase.co"))

        save_frontend_env(frontend_path, config)

        content = (frontend_path / ".env").read_text()

        # Verify structure comments exist
        assert "For Vercel Deployment" in content
        assert "For DevHand CLI Only" in content
