from __future__ import annotations

import json
from pathlib import Path

from models import Macro
from utils import ensure_dir, sanitize_filename
import json


def save_theme(theme: str, storage_dir: Path) -> Path:
    ensure_dir(storage_dir)
    settings_path = storage_dir / "settings.json"
    payload = {"theme": theme}
    with settings_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
    return settings_path


def load_theme(storage_dir: Path) -> str | None:
    settings_path = storage_dir / "settings.json"
    if not settings_path.exists():
        return None
    try:
        with settings_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload.get("theme")
    except Exception:
        return None


def save_macro_to_path(macro: Macro, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(macro.to_dict(), file, indent=2, ensure_ascii=False)
    return output_path


def load_macro_from_path(input_path: Path) -> Macro:
    with input_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return Macro.from_dict(payload)


def save_macro_default(macro: Macro, macros_dir: Path) -> Path:
    ensure_dir(macros_dir)
    filename = sanitize_filename(macro.name)
    output_path = macros_dir / f"{filename}_{macro.id[:8]}.json"
    return save_macro_to_path(macro, output_path)
