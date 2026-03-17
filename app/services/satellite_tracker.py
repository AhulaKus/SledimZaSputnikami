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
    ) -> tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """
        Возвращает два списка точек:
        - прошлый трек
        - будущий трек
        """
        now = datetime.now().astimezone()

        past_start = now - timedelta(minutes=minutes_back)
        future_end = now + timedelta(minutes=minutes_forward)

        past_total_sec = int((now - past_start).total_seconds())
        future_total_sec = int((future_end - now).total_seconds())

        past_steps = max(1, past_total_sec // step_sec)
        future_steps = max(1, future_total_sec // step_sec)

        past_times = [past_start + timedelta(seconds=i * step_sec) for i in range(past_steps + 1)]
        future_times = [now + timedelta(seconds=i * step_sec) for i in range(future_steps + 1)]

        t_past = self._ts.from_datetimes(past_times)
        t_future = self._ts.from_datetimes(future_times)

        past_geocentric = satellite.at(t_past)
        future_geocentric = satellite.at(t_future)

        past_subpoints = past_geocentric.subpoint()
        future_subpoints = future_geocentric.subpoint()

        past_points = list(zip(past_subpoints.latitude.degrees, past_subpoints.longitude.degrees))
        future_points = list(zip(future_subpoints.latitude.degrees, future_subpoints.longitude.degrees))

        return past_points, future_points