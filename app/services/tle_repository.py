from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from skyfield.api import load


@dataclass(frozen=True)
class TleCategory:
    name: str
    url: str


@dataclass(frozen=True)
class TleMeta:
    source_url: str
    downloaded_at_iso: str
    http_status: int
    etag: Optional[str]
    last_modified: Optional[str]
    sha256: str
    bytes: int


class TleRepository:
    def __init__(self, cache_dir: str = "tle_cache") -> None:
        self._cache: Dict[str, Dict[str, object]] = {}
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def load_category(self, category: TleCategory, reload: bool = False) -> Dict[str, object]:
        if (not reload) and (category.name in self._cache):
            return self._cache[category.name]

        local_tle = self._cache_dir / f"{self._safe_name(category.name)}.txt"
        local_meta = self._cache_dir / f"{self._safe_name(category.name)}.meta.json"

        if reload or (not local_tle.exists()):
            self._download_to_file(category.url, local_tle, local_meta)

        sats = load.tle_file(str(local_tle), reload=False)
        satellites = {sat.name: sat for sat in sats}
        self._cache[category.name] = satellites
        return satellites

    def read_meta(self, category: TleCategory) -> Optional[TleMeta]:
        local_meta = self._cache_dir / f"{self._safe_name(category.name)}.meta.json"
        if not local_meta.exists():
            return None
        data = json.loads(local_meta.read_text(encoding="utf-8"))
        return TleMeta(**data)

    @staticmethod
    def list_satellite_names(satellites: Dict[str, object]) -> List[str]:
        return sorted(satellites.keys())

    @staticmethod
    def _safe_name(name: str) -> str:
        return "".join(ch if ch.isalnum() else "_" for ch in name)

    @staticmethod
    def _sha256_bytes(b: bytes) -> str:
        h = hashlib.sha256()
        h.update(b)
        return h.hexdigest()

    @staticmethod
    def _now_iso_local() -> str:
        # ISO с timezone, чтобы было красиво для “актуальности”
        return datetime.now().astimezone().isoformat(timespec="seconds")

    @classmethod
    def _download_to_file(cls, url: str, tle_path: Path, meta_path: Path) -> None:
        headers = {
            "User-Agent": "Mozilla/5.0 (SatelliteTrackerApp)",
            "Accept": "text/plain,*/*",
            "Connection": "close",
        }

        last_exc: Exception | None = None
        for _ in range(3):
            try:
                r = requests.get(url, headers=headers, timeout=25)
                status = r.status_code
                r.raise_for_status()

                content = r.content
                tle_path.write_bytes(content)

                meta = TleMeta(
                    source_url=url,
                    downloaded_at_iso=cls._now_iso_local(),
                    http_status=status,
                    etag=r.headers.get("ETag"),
                    last_modified=r.headers.get("Last-Modified"),
                    sha256=cls._sha256_bytes(content),
                    bytes=len(content),
                )
                meta_path.write_text(json.dumps(meta.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
                return
            except Exception as e:
                last_exc = e

        raise RuntimeError(f"Failed to download TLE from {url}") from last_exc