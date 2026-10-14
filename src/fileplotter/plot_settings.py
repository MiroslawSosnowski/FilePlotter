from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fileplotter.models import default_plot_config


SETTINGS_FILENAME = "plot_settings.json"


def application_root() -> Path:
    """Return the directory that owns application-level settings.

    A PyInstaller one-file app is unpacked into a temporary directory, so
    ``__file__`` must not be used in frozen mode. ``sys.executable`` continues
    to point at the launched FilePlotter executable.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    entry_point = Path(sys.argv[0]).resolve()
    if entry_point.name.lower() == "main.py":
        return entry_point.parent
    return Path(__file__).resolve().parents[2]


def plot_settings_path(root: str | Path | None = None) -> Path:
    return Path(root).resolve() / SETTINGS_FILENAME if root else application_root() / SETTINGS_FILENAME


def load_plot_settings(root: str | Path | None = None) -> dict[str, Any]:
    config = default_plot_config()
    path = plot_settings_path(root)
    if not path.is_file():
        return config
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    if isinstance(payload, dict):
        config.update(payload)
    return config


def save_plot_settings(
    config: dict[str, Any], root: str | Path | None = None
) -> Path:
    path = plot_settings_path(root)
    payload = default_plot_config()
    payload.update(config)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path
