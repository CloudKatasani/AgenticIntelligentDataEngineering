"""Application configuration.

Everything the app needs to boot is resolved here, once, from the environment.
No other module reads ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_specs_root() -> Path:
    """Locate ``ade-agent-specs`` relative to this file.

    The catalog is the single source of truth for the fleet, so the app reads it
    straight from the repository rather than keeping a second copy.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "ade-agent-specs"
        if (candidate / "registry.yaml").exists():
            return candidate
    return here.parents[4] / "ade-agent-specs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADE_", env_file=".env", extra="ignore")

    app_name: str = "ADE Studio"
    environment: str = "development"

    # Where the 35 agent specs live.
    specs_root: Path = _default_specs_root()

    # Local state: artifacts, run journal, demo warehouse, saved connections.
    data_root: Path = Path(__file__).resolve().parents[2] / ".ade-studio-data"

    # Anthropic access. When unset the app still runs: the run engine falls back
    # to the deterministic simulation provider so a demo needs no credentials.
    anthropic_api_key: str | None = None
    default_model_id: str = "claude-opus-5"
    default_effort: str = "high"

    # Guardrails.
    default_cost_cap_usd: float = 5.0
    max_objects_per_run: int = 25
    max_sample_rows: int = 500

    # CORS origins for the Vite dev server.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @property
    def artifacts_dir(self) -> Path:
        return self.data_root / "artifacts"

    @property
    def runs_db_path(self) -> Path:
        return self.data_root / "runs.json"

    @property
    def connections_path(self) -> Path:
        return self.data_root / "connections.json"

    @property
    def spaces_path(self) -> Path:
        return self.data_root / "document_spaces.json"

    @property
    def uploads_dir(self) -> Path:
        return self.data_root / "uploads"

    @property
    def demo_warehouse_path(self) -> Path:
        return self.data_root / "demo_warehouse.duckdb"

    def ensure_dirs(self) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
