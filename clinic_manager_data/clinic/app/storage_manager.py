from __future__ import annotations

import os
import re
from pathlib import Path

from django.conf import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_FILE_NAME = "storage.txt"


def get_data_dir() -> Path:
    return Path(getattr(settings, "DATA_DIR", PROJECT_ROOT / "data"))


def get_storage_file_path() -> Path:
    return PROJECT_ROOT / STORAGE_FILE_NAME


def parse_storage_limit_mb(raw_text: str | None) -> int:
    if not raw_text:
        return 0

    match = re.search(r"(\d+(?:\.\d+)?)", raw_text)
    if not match:
        return 0

    try:
        value = int(float(match.group(1)))
    except (TypeError, ValueError):
        return 0

    return value if value > 0 else 0


def read_storage_limit_mb() -> int:
    storage_file = get_storage_file_path()
    if not storage_file.exists():
        return 0

    try:
        return parse_storage_limit_mb(storage_file.read_text(encoding="utf-8"))
    except OSError:
        return 0


def write_storage_limit_mb(limit_mb: int) -> Path:
    storage_file = get_storage_file_path()
    storage_file.write_text(f"size = {int(limit_mb)} MB\n", encoding="utf-8")
    return storage_file


def get_file_size_bytes(file_obj) -> int:
    if file_obj is None:
        return 0

    size = getattr(file_obj, "size", None)
    if size is not None:
        try:
            return int(size)
        except (TypeError, ValueError):
            pass

    if hasattr(file_obj, "getbuffer"):
        try:
            return file_obj.getbuffer().nbytes
        except Exception:
            pass

    if hasattr(file_obj, "read"):
        try:
            current_position = file_obj.tell() if hasattr(file_obj, "tell") else None
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
            content = file_obj.read()
            if current_position is not None and hasattr(file_obj, "seek"):
                file_obj.seek(current_position)
            return len(content)
        except Exception:
            return 0

    return 0


def folder_size_bytes(root_path: Path) -> int:
    total = 0
    if not root_path.exists():
        return total

    for current_root, _, files in os.walk(root_path):
        for file_name in files:
            file_path = Path(current_root) / file_name
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def human_readable_size(size_bytes: int) -> str:
    value = float(max(size_bytes, 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def get_storage_status(additional_bytes: int = 0) -> dict:
    limit_mb = read_storage_limit_mb()
    limit_bytes = max(limit_mb, 0) * 1024 * 1024
    data_dir = get_data_dir()
    used_bytes = folder_size_bytes(data_dir)
    projected_used_bytes = used_bytes + max(int(additional_bytes or 0), 0)
    available_bytes = max(0, limit_bytes - used_bytes)

    percent_used = 0.0
    if limit_bytes > 0:
        percent_used = min(100.0, (used_bytes / limit_bytes) * 100)

    return {
        "limit_mb": limit_mb,
        "limit_bytes": limit_bytes,
        "used_bytes": used_bytes,
        "used_mb": used_bytes / (1024 * 1024) if used_bytes else 0,
        "used_human": human_readable_size(used_bytes),
        "available_bytes": available_bytes,
        "available_mb": available_bytes / (1024 * 1024) if available_bytes else 0,
        "available_human": human_readable_size(available_bytes),
        "percent_used": round(percent_used, 2),
        "projected_used_bytes": projected_used_bytes,
        "projected_used_mb": projected_used_bytes / (1024 * 1024) if projected_used_bytes else 0,
        "projected_used_human": human_readable_size(projected_used_bytes),
        "can_store": projected_used_bytes <= limit_bytes,
        "data_dir": str(data_dir),
        "storage_file": str(get_storage_file_path()),
    }