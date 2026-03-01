from __future__ import annotations

from dataclasses import dataclass

from skyfield.api import load


@dataclass(frozen=True)
class SatelliteState:
    name: str
    lat_deg: float
    lon_deg: float
    alt_km: float


class SatelliteTracker:
    """
    Считает подспутниковую точку (lat/lon/alt) на 'сейчас'.
    """

    def get_state_now(self, satellite: object, name: str) -> SatelliteState:
        t = load.timescale().now()
        geocentric = satellite.at(t)
        subpoint = geocentric.subpoint()

        lat = float(subpoint.latitude.degrees)
        lon = float(subpoint.longitude.degrees)
        alt_km = float(subpoint.elevation.m) / 1000.0

        return SatelliteState(name=name, lat_deg=lat, lon_deg=lon, alt_km=alt_km)