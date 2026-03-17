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
        past_track_segments: list | None = None,
        future_track_segments: list | None = None,
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

        if past_track_segments:
            for seg in past_track_segments:
                folium.PolyLine(
                    locations=[[lat, lon] for (lat, lon) in seg],
                    weight=2,
                    opacity=0.45,
                    color="red",
                ).add_to(m)

        if future_track_segments:
            for seg in future_track_segments:
                folium.PolyLine(
                    locations=[[lat, lon] for (lat, lon) in seg],
                    weight=3,
                    opacity=0.9,
                    color="green",
                ).add_to(m)
        temp_path = os.path.abspath(self._cfg.temp_file)

        legend_html = """
        <div id="map-legend-wrapper" style="
            position: fixed;
            bottom: 30px;
            left: 30px;
            z-index: 9999;
            font-size: 13px;
        ">

            <div id="map-legend-content" onclick="hideLegend()" style="
                background-color: white;
                border: 2px solid gray;
                border-radius: 6px;
                padding: 10px;
                box-shadow: 2px 2px 6px rgba(0,0,0,0.2);
                cursor: pointer;
                display: block;
                min-width: 170px;
            ">
                <div><b>Обозначения</b></div>

                <div style="margin-top: 6px;">
                    <span style="display:inline-block; width:18px; height:3px; background:red; vertical-align:middle;"></span>
                    <span style="margin-left:8px;">Прошлый трек</span>
                </div>

                <div style="margin-top: 6px;">
                    <span style="display:inline-block; width:18px; height:3px; background:green; vertical-align:middle;"></span>
                    <span style="margin-left:8px;">Будущий трек</span>
                </div>

                <div style="margin-top: 6px;">
                    <span style="display:inline-block; width:18px; height:18px; background:rgba(0,0,255,0.25); border:1px solid blue; vertical-align:middle;"></span>
                    <span style="margin-left:8px;">Зона покрытия</span>
                </div>

                <div style="margin-top: 6px;">
                    <span style="display:inline-block; width:12px; height:12px; background:red; border-radius:50%; vertical-align:middle;"></span>
                    <span style="margin-left:8px;">Спутник</span>
                </div>
            </div>

            <button id="map-legend-button" onclick="showLegend()" style="
                display: none;
                background-color: white;
                border: 2px solid gray;
                border-radius: 6px;
                padding: 6px 10px;
                cursor: pointer;
                font-size: 13px;
                box-shadow: 2px 2px 6px rgba(0,0,0,0.2);
            ">
                Легенда
            </button>
        </div>

        <script>
        function hideLegend() {
            document.getElementById('map-legend-content').style.display = 'none';
            document.getElementById('map-legend-button').style.display = 'block';
        }

        function showLegend() {
            document.getElementById('map-legend-content').style.display = 'block';
            document.getElementById('map-legend-button').style.display = 'none';
        }
        </script>
        """
        root = m.get_root()
        root.html.add_child(folium.Element(legend_html))

        m.save(temp_path)
        return temp_path