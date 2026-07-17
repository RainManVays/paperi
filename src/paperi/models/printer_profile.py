from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from paperi.models.enums import PrinterModel


@dataclass
class PrinterProfile:
    id: str
    name: str
    mac: str
    model: PrinterModel
    default_concentration: int = 1
    default_break: int = 60
    chunk_height_px: int = 220
    last_connected_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["model"] = self.model.value
        data["last_connected_at"] = (
            self.last_connected_at.isoformat() if self.last_connected_at else None
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrinterProfile:
        last_connected_at = data.get("last_connected_at")
        return cls(
            id=data["id"],
            name=data["name"],
            mac=data["mac"],
            model=PrinterModel(data["model"]),
            default_concentration=data.get("default_concentration", 1),
            default_break=data.get("default_break", 60),
            chunk_height_px=data.get("chunk_height_px", 220),
            last_connected_at=datetime.fromisoformat(last_connected_at)
            if last_connected_at
            else None,
        )
