from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from periprint.utils.paths import config_dir


@dataclass
class AppConfig:
    active_printer_id: str | None = None
    auto_connect_on_start: bool = True
    default_chunk_height_px: int = 220
    theme: str = "dark"
    log_level: str = "INFO"


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (config_dir() / "config.json")

    def load(self) -> AppConfig:
        if not self._path.exists():
            return AppConfig()
        data = json.loads(self._path.read_text())
        return AppConfig(**data)

    def save(self, config: AppConfig) -> None:
        self._path.write_text(json.dumps(asdict(config), indent=2))
