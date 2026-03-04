from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple

from skyfield.api import load
from skyfield.sgp4lib import EarthSatellite


@dataclass(frozen=True)
class SatelliteState:
    name: str
    lat_deg: float
    lon_deg: float
    alt_km: float


class SatelliteTracker:
    """
    Считает подспутниковую точку (lat/lon/alt) и ground track.
    """

    def __init__(self) -> None:
        self._ts = load.timescale()

    def get_state_now(self, satellite: EarthSatellite, name: str) -> SatelliteState:
        t = self._ts.now()
        geocentric = satellite.at(t)
        subpoint = geocentric.subpoint()

        return SatelliteState(
            name=name,
            lat_deg=float(subpoint.latitude.degrees),
            lon_deg=float(subpoint.longitude.degrees),
            alt_km=float(subpoint.elevation.m) / 1000.0,
        )

    def get_ground_track(
        self,
        satellite: EarthSatellite,
        minutes_back: int = 60,
        minutes_forward: int = 60,
        step_sec: int = 60,
    ) -> List[Tuple[float, float]]:
        """
        Возвращает список (lat, lon) для трека: прошлое + будущее.
        """
        now = datetime.now().astimezone()

        start = now - timedelta(minutes=minutes_back)
        end = now + timedelta(minutes=minutes_forward)

        total_sec = int((end - start).total_seconds())
        steps = max(1, total_sec // step_sec)

        times = [start + timedelta(seconds=i * step_sec) for i in range(steps + 1)]
        t = self._ts.from_datetimes(times)

        geocentric = satellite.at(t)
        subpoints = geocentric.subpoint()

        lats = subpoints.latitude.degrees
        lons = subpoints.longitude.degrees

        return list(zip(lats, lons))