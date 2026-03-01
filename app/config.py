from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    window_title: str = "МТУСИ: КАЗАХИ РУЛЯТТТ!!!! ЛЮБЛЮ ШАМАНА!"
    width: int = 1200
    height: int = 850
    temp_map_file: str = "temp_map_final.html"
    map_tiles: str = "CartoDB positron"
    min_zoom: int = 2
    default_zoom: int = 2

    # Ограничение по фолие (чтобы полигоны нормально рисовались)
    max_lat: float = 85.0
    min_lat: float = -85.0

    # Радиус Земли
    earth_radius_km: float = 6371.0


TLE_CATEGORIES = {
    "GPS (Навигация)": "https://celestrak.org/NORAD/elements/gps-ops.txt",
    "Космические станции (МКС)": "https://celestrak.org/NORAD/elements/stations.txt",
    "Метеоспутники (Weather)": "https://celestrak.org/NORAD/elements/weather.txt",
    "ГЛОНАСС (Навигация)": "https://celestrak.org/NORAD/elements/glo-ops.txt",
    "Спутники связи (Molniya)": "https://celestrak.org/NORAD/elements/molniya.txt",
    "Геостационарные (ТВ)": "https://celestrak.org/NORAD/elements/geo.txt",
    "Starlink": "https://celestrak.org/NORAD/elements/starlink.txt",
}