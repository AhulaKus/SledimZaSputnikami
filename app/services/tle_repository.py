from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import requests
from skyfield.api import load


@dataclass(frozen=True)
class TleCategory:
    name: str
    url: str


class TleRepository:
    def __init__(self, cache_dir: str = "tle_cache") -> None:
        self._cache: Dict[str, Dict[str, object]] = {}
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def load_category(self, category: TleCategory, reload: bool = False) -> Dict[str, object]:
        if (not reload) and (category.name in self._cache):
            return self._cache[category.name]

        local_path = self._cache_dir / f"{self._safe_name(category.name)}.txt"

        if reload or (not local_path.exists()):
            self._download_to_file(category.url, local_path)

        # ВАЖНО: парсим локальный файл, без сети
        sats = load.tle_file(str(local_path), reload=False)
        satellites = {sat.name: sat for sat in sats}
        self._cache[category.name] = satellites
        return satellites

    @staticmethod
    def list_satellite_names(satellites: Dict[str, object]) -> List[str]:
        return sorted(satellites.keys())

    @staticmethod
    def _safe_name(name: str) -> str:
        return "".join(ch if ch.isalnum() else "_" for ch in name)

    @staticmethod
    def _download_to_file(url: str, path: Path) -> None:
        headers = {
            "User-Agent": "Mozilla/5.0 (SatelliteTrackerApp)",
            "Accept": "text/plain,*/*",
            "Connection": "close",
        }
        # простые ретраи
        last_exc: Exception | None = None
        for _ in range(3):
            try:
                r = requests.get(url, headers=headers, timeout=20)
                r.raise_for_status()
                path.write_bytes(r.content)
                return
            except Exception as e:
                last_exc = e
        raise RuntimeError(f"Failed to download TLE from {url}") from last_exc