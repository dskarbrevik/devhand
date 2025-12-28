"""Configuration file handling using .env files in FE and BE repos."""

import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    """Database configuration (from frontend .env)."""

    url: Optional[str] = None
    public_key: Optional[str] = None  # sb_publishable_* (new) or legacy anon JWT
    secret_key: Optional[str] = None  # sb_secret_* (new) or legacy service_role JWT
    password: Optional[str] = None
    project_ref: Optional[str] = None
    access_token: Optional[str] = None  # For Supabase CLI


class ProjectConfig(BaseModel):
    """Project paths configuration."""

    frontend_path: Optional[str] = None
    backend_path: Optional[str] = None


class PreferencesConfig(BaseModel):
    """User preferences."""

    disable_detection_warnings: bool = False
    auto_install_dependencies: bool = True


class Config(BaseModel):
    """Main configuration."""

    project: ProjectConfig = ProjectConfig()
    db: DatabaseConfig = DatabaseConfig()
    preferences: PreferencesConfig = PreferencesConfig()


def _load_env_file(env_path: Path) -> dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars = {}
    if not env_path.exists():
        return env_vars

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes if present
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value

    return env_vars


def load_config(
    workspace_root: Path,
    frontend_path: Optional[Path] = None,
    backend_path: Optional[Path] = None,
) -> Config:
    """Load configuration from .env files in frontend and backend directories.

    Frontend .env contains:
    - NEXT_PUBLIC_SUPABASE_URL
    - NEXT_PUBLIC_SUPABASE_KEY (public/anon key for frontend)
    - SUPABASE_SECRET_KEY (secret/service_role key for CLI operations)
    - SUPABASE_DB_PASSWORD
    - SUPABASE_ACCESS_TOKEN
    - NEXT_PUBLIC_API_URL

    Backend .env contains backend-specific variables.
    """
    config_data: dict[str, dict] = {
        "project": {},
        "db": {},
        "preferences": {},
    }

    # Load from frontend .env if it exists
    if frontend_path:
        fe_env_path = frontend_path / ".env"
        fe_env = _load_env_file(fe_env_path)

        if fe_env:
            # Map frontend env vars to config structure
            if "NEXT_PUBLIC_SUPABASE_URL" in fe_env:
                config_data["db"]["url"] = fe_env["NEXT_PUBLIC_SUPABASE_URL"]
                # Extract project_ref from URL
                match = re.search(
                    r"https://([^.]+)\.supabase\.co", fe_env["NEXT_PUBLIC_SUPABASE_URL"]
                )
                if match:
                    config_data["db"]["project_ref"] = match.group(1)

            if "NEXT_PUBLIC_SUPABASE_KEY" in fe_env:
                config_data["db"]["public_key"] = fe_env["NEXT_PUBLIC_SUPABASE_KEY"]

            if "SUPABASE_SECRET_KEY" in fe_env:
                config_data["db"]["secret_key"] = fe_env["SUPABASE_SECRET_KEY"]

            if "SUPABASE_DB_PASSWORD" in fe_env:
                config_data["db"]["password"] = fe_env["SUPABASE_DB_PASSWORD"]

            if "SUPABASE_ACCESS_TOKEN" in fe_env:
                config_data["db"]["access_token"] = fe_env["SUPABASE_ACCESS_TOKEN"]

    # Load from backend .env if needed (for future use)
    if backend_path:
        be_env_path = backend_path / ".env"
        _load_env_file(be_env_path)
        # Backend-specific config can be added here as needed

    # Store paths
    if frontend_path:
        config_data["project"]["frontend_path"] = str(frontend_path)
    if backend_path:
        config_data["project"]["backend_path"] = str(backend_path)

    return Config(**config_data)


def save_frontend_env(
    frontend_path: Path, config: Config, api_url: Optional[str] = None
) -> None:
    """Save database configuration to frontend .env file."""
    env_path = frontend_path / ".env"

    # Read existing .env if it exists
    existing_env = {}
    if env_path.exists():
        existing_env = _load_env_file(env_path)

    # Update with new values (for deployment to Vercel)
    if config.db.url:
        existing_env["NEXT_PUBLIC_SUPABASE_URL"] = config.db.url
    if config.db.public_key:
        existing_env["NEXT_PUBLIC_SUPABASE_KEY"] = config.db.public_key
    if api_url:
        existing_env["NEXT_PUBLIC_API_URL"] = api_url

    # Update with CLI-only values (not needed for Vercel deployment)
    if config.db.secret_key:
        existing_env["SUPABASE_SECRET_KEY"] = config.db.secret_key
    if config.db.password:
        existing_env["SUPABASE_DB_PASSWORD"] = config.db.password
    if config.db.access_token:
        existing_env["SUPABASE_ACCESS_TOKEN"] = config.db.access_token

    # Write back to .env
    with open(env_path, "w") as f:
        f.write("# Frontend Environment Variables\n\n")
        f.write("# === For Vercel Deployment ===\n")
        f.write("# Copy these variables to your Vercel project settings:\n\n")
        if "NEXT_PUBLIC_API_URL" in existing_env:
            f.write(f"NEXT_PUBLIC_API_URL={existing_env['NEXT_PUBLIC_API_URL']}\n")
        if "NEXT_PUBLIC_SUPABASE_URL" in existing_env:
            f.write(
                f"NEXT_PUBLIC_SUPABASE_URL={existing_env['NEXT_PUBLIC_SUPABASE_URL']}\n"
            )
        if "NEXT_PUBLIC_SUPABASE_KEY" in existing_env:
            f.write(
                f"NEXT_PUBLIC_SUPABASE_KEY={existing_env['NEXT_PUBLIC_SUPABASE_KEY']}\n"
            )

        f.write("\n# === After Deploying to Vercel ===\n")
        f.write("# Add your Vercel deployment URL below (for validation):\n")
        f.write("# VERCEL_URL=https://your-app.vercel.app\n")

        f.write("\n# === For DevHand CLI Only ===\n")
        f.write(
            "# These are used by 'dh db' commands and are NOT needed in Vercel:\n\n"
        )
        if "SUPABASE_SECRET_KEY" in existing_env:
            f.write(f"SUPABASE_SECRET_KEY={existing_env['SUPABASE_SECRET_KEY']}\n")
        if "SUPABASE_DB_PASSWORD" in existing_env:
            f.write(f"SUPABASE_DB_PASSWORD={existing_env['SUPABASE_DB_PASSWORD']}\n")
        if "SUPABASE_ACCESS_TOKEN" in existing_env:
            f.write(f"SUPABASE_ACCESS_TOKEN={existing_env['SUPABASE_ACCESS_TOKEN']}\n")


def save_backend_env(backend_path: Path, config: Config) -> None:
    """Save backend configuration to backend .env file."""
    env_path = backend_path / ".env"

    # Read existing .env if it exists
    if env_path.exists():
        _load_env_file(env_path)

    # Backend-specific variables can be added here as needed
    # For now, keeping it minimal

    # Write back to .env
    with open(env_path, "w") as f:
        f.write("# Backend Environment Variables\n")
        f.write("# Copy these to your Railway deployment settings\n\n")
        # Add any backend-specific variables here
