from __future__ import annotations

import json
import uuid
from pathlib import Path

from paperi.models.enums import PrinterModel
from paperi.models.printer_profile import PrinterProfile
from paperi.utils.paths import config_dir


class PrinterManager:
    """Owns saved PrinterProfile persistence. No Bluetooth connection logic
    here — that's PeripageClient's job (Stage 2)."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (config_dir() / "printers.json")
        self._profiles: dict[str, PrinterProfile] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        data = json.loads(self._path.read_text())
        for item in data:
            profile = PrinterProfile.from_dict(item)
            self._profiles[profile.id] = profile

    def _save(self) -> None:
        data = [profile.to_dict() for profile in self._profiles.values()]
        self._path.write_text(json.dumps(data, indent=2))

    def list_profiles(self) -> list[PrinterProfile]:
        return list(self._profiles.values())

    def get_profile(self, profile_id: str) -> PrinterProfile | None:
        return self._profiles.get(profile_id)

    def add_profile(
        self,
        name: str,
        mac: str,
        model: PrinterModel,
        default_concentration: int = 1,
        default_break: int = 60,
        chunk_height_px: int = 220,
    ) -> PrinterProfile:
        profile = PrinterProfile(
            id=str(uuid.uuid4()),
            name=name,
            mac=mac,
            model=model,
            default_concentration=default_concentration,
            default_break=default_break,
            chunk_height_px=chunk_height_px,
        )
        self._profiles[profile.id] = profile
        self._save()
        return profile

    def update_profile(self, profile: PrinterProfile) -> None:
        self._profiles[profile.id] = profile
        self._save()

    def remove_profile(self, profile_id: str) -> None:
        self._profiles.pop(profile_id, None)
        self._save()
