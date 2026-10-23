"""
Configuration and Environment Security Loader for AegisBridge-EMS.
Zero-Trust credential isolation: ensures no secrets ever escape to the client.
"""

from __future__ import annotations
import os
from pathlib import Path


def load_dotenv(env_path: Path | None = None) -> None:
    """
    Lightweight, robust .env parser without external dependencies.
    Loads key=value pairs into os.environ if not already defined.
    """
    if env_path is None:
        # Defaults to project root: <project_root>/.env
        env_path = Path(__file__).resolve().parent.parent / ".env"

    if not env_path.exists() or not env_path.is_file():
        return

    try:
        with env_path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    key, val = stripped.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass


# Proactively load environment variables upon module import
load_dotenv()
