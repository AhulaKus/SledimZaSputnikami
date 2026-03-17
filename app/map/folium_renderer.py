from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import folium


@dataclass(frozen=True)
class MapRenderConfig:
    tiles: str
    min_zoom: int
    zoom_start: int
    temp_file: str


class FoliumMapRenderer:
    def __init__(self, cfg: MapRenderConfig) -> None:
        self._cfg = cfg

    def render(
        self,
        lat: float,
        lon: float,
        sat_name: str,
        polygons: List[List[List[float]]],
        popup_html: Optional[str] = None,
        track_segments: list | None = None
    ) -> str:
        m = folium.Map(
            location=[lat, lon],
            zoom_start=self._cfg.zoom_start,
            tiles=self._cfg.tiles,
            min_zoom=self._cfg.min_zoom,
        )

        folium.Marker(
            location=[lat, lon],
            popup=popup_html or f"<b>{sat_name}</b>",
            icon=folium.Icon(color="red", icon="rocket", prefix="fa"),
        ).add_to(m)

        for poly in polygons:
            folium.Polygon(
                locations=poly,
                color="blue",
                weight=2,
                fill=True,
                fill_color="blue",
                fill_opacity=0.25,
            ).add_to(m)

        if track_segments:
            for seg in track_segments:
                folium.PolyLine(
                    locations=[[pt[0], pt[1]] for pt in seg],
                    weight=2,
                    opacity=0.8,
                ).add_to(m)

        temp_path = os.path.abspath(self._cfg.temp_file)
        if track_segments:
            for seg in track_segments:
                folium.PolyLine(
                    locations=[[lat, lon] for (lat, lon) in seg],
                    weight=2,
                    opacity=0.8,
                ).add_to(m)
        print("RENDER track:", 0 if not track_segments else sum(len(s) for s in track_segments))
        m.save(temp_path)
        return temp_path