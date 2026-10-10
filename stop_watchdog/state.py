"""Local persistence of the last-known-good protective stop for each symbol,
so a process restart doesn't forget what it was protecting."""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass(eq=True)
class StopSnapshot:
    order_type: str      # "STP" or "STP LMT"
    aux_price: float
    lmt_price: Optional[float]
    qty: int
    outside_rth: bool


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self._data: dict[str, StopSnapshot] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text())
        self._data = {sym: StopSnapshot(**fields) for sym, fields in raw.items()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {sym: asdict(snap) for sym, snap in self._data.items()}
        self.path.write_text(json.dumps(raw, indent=2))

    def get(self, symbol: str) -> Optional[StopSnapshot]:
        return self._data.get(symbol)

    def set(self, symbol: str, snapshot: StopSnapshot) -> None:
        self._data[symbol] = snapshot
        self.save()

    def clear(self, symbol: str) -> None:
        if symbol in self._data:
            del self._data[symbol]
            self.save()

    def symbols(self) -> list[str]:
        return list(self._data.keys())
