"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    devin_api_key: str = field(
        default_factory=lambda: os.environ.get("DEVIN_API_KEY", "")
    )
    devin_org_id: str = field(
        default_factory=lambda: os.environ.get("DEVIN_ORG_ID", "")
    )
    devin_api_base: str = field(
        default_factory=lambda: os.environ.get(
            "DEVIN_API_BASE", "https://api.devin.ai"
        )
    )
    github_webhook_secret: str = field(
        default_factory=lambda: os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    )
    target_repo: str = field(
        default_factory=lambda: os.environ.get("TARGET_REPO", "GWeale/superset")
    )
    trigger_label: str = field(
        default_factory=lambda: os.environ.get("TRIGGER_LABEL", "devin:ready")
    )
    database_path: str = field(
        default_factory=lambda: os.environ.get("DATABASE_PATH", "runs.db")
    )
    poll_interval_seconds: int = field(
        default_factory=lambda: int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
    )


def get_settings() -> Settings:
    return Settings()
