from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def generate_id() -> str:
    return str(uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_app_storage_dir(app_name: str, fallback_dir: Path) -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return ensure_dir(Path(local_app_data) / app_name)
    return ensure_dir(fallback_dir)


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return cleaned or "macro"


def parse_speed(value: str) -> float:
    normalized = value.lower().replace("x", "").strip()
    speed = float(normalized)
    if speed <= 0:
        raise ValueError("Velocidade deve ser maior que zero")
    return speed


def parse_repetitions(value: str) -> int:
    repetitions = int(value)
    if repetitions < 1:
        raise ValueError("Repetições deve ser >= 1")
    return repetitions
