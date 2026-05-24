from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class Settings:
    cpa_base_url: str = "http://127.0.0.1:3000"
    cpa_management_key: str = ""
    interval_minutes: int = 240
    auto_start: bool = True
    concurrency: int = 4
    timeout_seconds: int = 20
    quota_threshold: float = 100.0
    notify_on_success: bool = True
    notify_on_abnormal: bool = True
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_api_base: str = "https://api.telegram.org"
    bark_enabled: bool = False
    bark_server: str = "https://api.day.app"
    bark_device_key: str = ""
    bark_group: str = "CPA Codex Inspection"

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("cpa_management_key", "telegram_bot_token", "bark_device_key"):
            data[key] = mask_secret(data.get(key, ""))
        return data


def mask_secret(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def settings_from_env() -> Settings:
    return Settings(
        cpa_base_url=os.getenv("CPA_BASE_URL", Settings.cpa_base_url).strip(),
        cpa_management_key=os.getenv("CPA_MANAGEMENT_KEY", "").strip(),
        interval_minutes=parse_int(os.getenv("INSPECTION_INTERVAL_MINUTES"), 240, 1, 60 * 24 * 7),
        auto_start=parse_bool(os.getenv("AUTO_START"), True),
        concurrency=parse_int(os.getenv("INSPECTION_CONCURRENCY"), 4, 1, 32),
        timeout_seconds=parse_int(os.getenv("INSPECTION_TIMEOUT_SECONDS"), 20, 1, 300),
        quota_threshold=parse_float(os.getenv("QUOTA_THRESHOLD"), 100.0, 0.0, 100.0),
        notify_on_success=parse_bool(os.getenv("NOTIFY_ON_SUCCESS"), True),
        notify_on_abnormal=parse_bool(os.getenv("NOTIFY_ON_ABNORMAL"), True),
        telegram_enabled=parse_bool(os.getenv("TELEGRAM_ENABLED"), False),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        telegram_api_base=os.getenv("TELEGRAM_API_BASE", Settings.telegram_api_base).strip(),
        bark_enabled=parse_bool(os.getenv("BARK_ENABLED"), False),
        bark_server=os.getenv("BARK_SERVER", Settings.bark_server).strip(),
        bark_device_key=os.getenv("BARK_DEVICE_KEY", "").strip(),
        bark_group=os.getenv("BARK_GROUP", Settings.bark_group).strip(),
    )


def merge_settings(current: Settings, patch: dict[str, Any]) -> Settings:
    data = asdict(current)
    for key, value in patch.items():
        if key not in data:
            continue
        if key in ("cpa_management_key", "telegram_bot_token", "bark_device_key"):
            text = str(value or "").strip()
            if not text or "*" in text:
                continue
            data[key] = text
        elif isinstance(data[key], bool):
            data[key] = bool(value)
        elif isinstance(data[key], int):
            data[key] = parse_int(value, data[key], 1, 60 * 24 * 7)
        elif isinstance(data[key], float):
            data[key] = parse_float(value, data[key], 0.0, 100.0)
        else:
            data[key] = str(value or "").strip()

    data["concurrency"] = max(1, min(32, int(data["concurrency"])))
    data["timeout_seconds"] = max(1, min(300, int(data["timeout_seconds"])))
    data["interval_minutes"] = max(1, min(60 * 24 * 7, int(data["interval_minutes"])))
    data["quota_threshold"] = max(0.0, min(100.0, float(data["quota_threshold"])))
    return Settings(**data)


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def parse_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def parse_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))
