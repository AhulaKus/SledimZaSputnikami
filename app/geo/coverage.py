from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class CoverageResult:
    radius_km: float
    d_rad: float
    polygons: List[List[List[float]]]  # list of polygons, polygon = list of [lat, lon]


def coverage_radius(earth_radius_km: float, alt_km: float) -> Tuple[float, float]:
    """
    Возвращает (radius_km, d_rad) где d_rad — угловой радиус покрытия на сфере.
    """
    if alt_km <= 0:
        return 0.0, 0.0

    val = earth_radius_km / (earth_radius_km + alt_km)
    if val > 1:
        val = 1
    d_rad = math.acos(val)
    return d_rad * earth_radius_km, d_rad


def get_lat_for_lon(lat_center_deg: float, dlon_deg: float, angular_radius_rad: float) -> List[float]:
    """
    Аналитическое решение с защитой от 'мертвых зон' на обратной стороне Земли.
    Возвращает 0..2 валидных широты для заданной разницы долгот.
    """
    lat1 = math.radians(lat_center_deg)
    dlon = math.radians(dlon_deg)
    C = math.cos(angular_radius_rad)
    A = math.sin(lat1)
    B = math.cos(lat1) * math.cos(dlon)

    R_eq = math.sqrt(A**2 + B**2)
    if R_eq == 0:
        return []

    ratio = C / R_eq
    ratio = max(-1.0, min(1.0, ratio))

    alpha = math.atan2(B, A)
    val1 = math.asin(ratio)
    val2 = math.pi - val1

    lat2_1 = math.degrees(val1 - alpha)
    lat2_2 = math.degrees(val2 - alpha)

    # нормализация в [-180, 180]
    lat2_1 = (lat2_1 + 180) % 360 - 180
    lat2_2 = (lat2_2 + 180) % 360 - 180

    valid_lats: List[float] = []
    if -90 <= lat2_1 <= 90:
        valid_lats.append(lat2_1)
    if -90 <= lat2_2 <= 90:
        valid_lats.append(lat2_2)
    return valid_lats


def get_continuous_circle(
    lat: float,
    lon: float,
    radius_km: float,
    earth_radius_km: float,
    min_lat: float,
    max_lat: float,
) -> List[List[float]]:
    coords: List[List[float]] = []
    lat1, lon1 = math.radians(lat), math.radians(lon)
    d = radius_km / earth_radius_km

    brng = 0.0
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brng))
    lon2 = lon1 + math.atan2(
        math.sin(brng) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )

    prev_lon = math.degrees(lon2)
    while prev_lon - lon < -180:
        prev_lon += 360
    while prev_lon - lon > 180:
        prev_lon -= 360

    coords.append([max(min_lat, min(max_lat, math.degrees(lat2))), prev_lon])

    for brng_deg in range(2, 361, 2):
        brng = math.radians(brng_deg)
        lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brng))
        lon2 = lon1 + math.atan2(
            math.sin(brng) * math.sin(d) * math.cos(lat1),
            math.cos(d) - math.sin(lat1) * math.sin(lat2),
        )

        curr_lon = math.degrees(lon2)
        while curr_lon - prev_lon < -180:
            curr_lon += 360
        while curr_lon - prev_lon > 180:
            curr_lon -= 360

        coords.append([max(min_lat, min(max_lat, math.degrees(lat2))), curr_lon])
        prev_lon = curr_lon

    return coords


def build_coverage_polygons(
    lat: float,
    lon: float,
    alt_km: float,
    earth_radius_km: float,
    min_lat: float,
    max_lat: float,
) -> CoverageResult:
    radius_km, d_rad = coverage_radius(earth_radius_km, alt_km)
    polygons_to_draw: List[List[List[float]]] = []

    if radius_km <= 10:
        return CoverageResult(radius_km=radius_km, d_rad=d_rad, polygons=[])

    dist_to_north_rad = math.radians(90.0 - lat)
    dist_to_south_rad = math.radians(lat - (-90.0))

    covers_north = d_rad >= dist_to_north_rad
    covers_south = d_rad >= dist_to_south_rad

    if covers_north and covers_south:
        coords: List[List[float]] = []
        for lon_deg in range(-180, 181, 5):
            coords.append([max_lat, float(lon_deg)])
        for lon_deg in range(180, -181, -5):
            coords.append([min_lat, float(lon_deg)])
        polygons_to_draw.append(coords)

    elif covers_north:
        coords = []
        for lon_deg in range(-180, 181, 2):
            lats = get_lat_for_lon(lat, lon_deg - lon, d_rad)
            bound_lat = min(lats) if lats else min_lat
            bound_lat = max(min_lat, min(max_lat, bound_lat))
            coords.append([bound_lat, float(lon_deg)])
        for lon_deg in range(180, -181, -2):
            coords.append([max_lat, float(lon_deg)])
        polygons_to_draw.append(coords)

    elif covers_south:
        coords = []
        for lon_deg in range(-180, 181, 2):
            lats = get_lat_for_lon(lat, lon_deg - lon, d_rad)
            bound_lat = max(lats) if lats else max_lat
            bound_lat = max(min_lat, min(max_lat, bound_lat))
            coords.append([bound_lat, float(lon_deg)])
        for lon_deg in range(180, -181, -2):
            coords.append([min_lat, float(lon_deg)])
        polygons_to_draw.append(coords)

    else:
        coords = get_continuous_circle(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            earth_radius_km=earth_radius_km,
            min_lat=min_lat,
            max_lat=max_lat,
        )
        polygons_to_draw.append(coords)

        lons = [pt[1] for pt in coords]
        if max(lons) > 180:
            polygons_to_draw.append([[pt[0], pt[1] - 360] for pt in coords])
        if min(lons) < -180:
            polygons_to_draw.append([[pt[0], pt[1] + 360] for pt in coords])

    return CoverageResult(radius_km=radius_km, d_rad=d_rad, polygons=polygons_to_draw)