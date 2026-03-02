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

        # Для UI
        self.last_source: str = "unknown"     # "network" | "cache" | "unknown"
        self.last_error: Optional[str] = None # ошибка обновления (если была)

    def load_category(self, category: TleCategory, reload: bool = False) -> Dict[str, object]:
        self.last_source = "unknown"
        self.last_error = None

        # 1) Memory cache
        if (not reload) and (category.name in self._cache):
            self.last_source = "cache"
            return self._cache[category.name]

        tle_path, meta_path = self._paths_for(category)

        # 2) Disk cache (если не просили reload)
        if (not reload) and tle_path.exists():
            self.last_source = "cache"
            sats = self._load_from_disk(category, tle_path, meta_path)
            self._cache[category.name] = sats
            return sats

        # 3) Network attempt (reload=True или файла нет)
        downloaded = self._try_download(category, tle_path, meta_path)
        self.last_source = "network" if downloaded else "cache"

        sats = self._load_from_disk(category, tle_path, meta_path)
        self._cache[category.name] = sats
        return sats

    # --- НОВОЕ: read_meta (твой же метод, просто возвращён обратно) ---
    def read_meta(self, category: TleCategory) -> Optional[TleMeta]:
        _, meta_path = self._paths_for(category)
        if not meta_path.exists():
            return None
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return TleMeta(**data)

    # ---------- helpers (для красоты и читаемости) ----------

    def _paths_for(self, category: TleCategory) -> tuple[Path, Path]:
        safe = self._safe_name(category.name)
        return (
            self._cache_dir / f"{safe}.txt",
            self._cache_dir / f"{safe}.meta.json",
        )

    def _load_from_disk(self, category: TleCategory, tle_path: Path, meta_path: Path) -> Dict[str, object]:
        if not tle_path.exists():
            raise FileNotFoundError(f"TLE file not found: {tle_path}")

        self._ensure_meta(category, tle_path, meta_path)

        sats = load.tle_file(str(tle_path), reload=False)
        return {sat.name: sat for sat in sats}

    def _try_download(self, category: TleCategory, tle_path: Path, meta_path: Path) -> bool:
        """
        True  -> скачали из сети
        False -> не скачали, но есть кэш (fallback)
        raise -> не скачали и кэша нет
        """
        try:
            self._download_to_file(category.url, tle_path, meta_path)
            return True
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            if tle_path.exists():
                return False
            raise

    def _ensure_meta(self, category: TleCategory, tle_path: Path, meta_path: Path) -> None:
        if meta_path.exists():
            return

        content = tle_path.read_bytes()
        meta = TleMeta(
            source_url=category.url,
            downloaded_at_iso=self._now_iso_local(),
            http_status=0,
            etag=None,
            last_modified=None,
            sha256=self._sha256_bytes(content),
            bytes=len(content),
        )
        meta_path.write_text(json.dumps(meta.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- твои утилиты (без изменений) ---
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