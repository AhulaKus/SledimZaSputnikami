from __future__ import annotations

from datetime import datetime

from typing import Dict, List, Tuple

import time

from PyQt5.QtCore import QUrl, Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QLabel,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QApplication,
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

import traceback

from app.config import AppConfig, TLE_CATEGORIES
from app.map.folium_renderer import FoliumMapRenderer, MapRenderConfig
from app.services.tle_repository import TleCategory, TleRepository
from app.services.satellite_tracker import SatelliteTracker
from app.geo.coverage import build_coverage_polygons

from pathlib import Path


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig) -> None:
        super().__init__()
        self._cfg = cfg

        self.setWindowTitle(cfg.window_title)
        self.resize(cfg.width, cfg.height)

        # зависимости (можно потом сделать DI/контейнер, но пока так ок)
        self._tle_repo = TleRepository()
        self._tracker = SatelliteTracker()
        self._renderer = FoliumMapRenderer(
            MapRenderConfig(
                tiles=cfg.map_tiles,
                min_zoom=cfg.min_zoom,
                zoom_start=cfg.default_zoom,
                temp_file=cfg.temp_map_file,
            )
        )

        self._categories = {name: TleCategory(name=name, url=url) for name, url in TLE_CATEGORIES.items()}
        self._current_satellites: Dict[str, object] = {}

        self._init_ui()
        self._load_category(self.combo_category.currentText())

        self._timer = QTimer(self)
        self._timer.setInterval(2000)  # 2 секунды, можно поменять
        self._timer.timeout.connect(self._tick)

        self._track_segments = None
        self._track_last_update_ts = 0.0

        self._selected_sat_name: str | None = None
        self._track_sat_name: str | None = None

    def _start_tracking(self) -> None:
        if not self._selected_sat_name:
            self.sat_label.setText("Сначала выберите спутник")
            return
        self._timer.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _stop_tracking(self) -> None:
        self._timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _tick(self) -> None:
        # если спутник не выбран — ничего не делаем
        if not self._selected_sat_name:
            return
        # обновляем ту же самую карту
        self._update_map(self._selected_sat_name)


    def _init_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        control_panel = QWidget()
        control_layout = QHBoxLayout()
        control_panel.setLayout(control_layout)
        control_panel.setStyleSheet("background-color: #f5f5f5; padding: 5px; border-bottom: 1px solid #ddd;")

        control_layout.addWidget(QLabel("1. Категория:"))
        self.combo_category = QComboBox()
        self.combo_category.addItems(self._categories.keys())
        self.combo_category.currentTextChanged.connect(self._load_category)
        control_layout.addWidget(self.combo_category, stretch=1)

        control_layout.addWidget(QLabel("2. Спутник:"))
        self.combo_sat = QComboBox()
        self.combo_sat.currentTextChanged.connect(self._update_map)
        control_layout.addWidget(self.combo_sat, stretch=1)

        btn_exit = QPushButton("Выход")
        btn_exit.setStyleSheet(
            "background-color: #d32f2f; color: white; border-radius: 3px; font-weight: bold; padding: 5px 15px;"
        )
        btn_exit.clicked.connect(self.close)
        control_layout.addWidget(btn_exit)

        main_layout.addWidget(control_panel)

        self.btn_retry = QPushButton("Обновить TLE")
        self.btn_retry.clicked.connect(self._retry_load_current_category)
        control_layout.addWidget(self.btn_retry)

        self.btn_start = QPushButton("Старт")
        self.btn_start.clicked.connect(self._start_tracking)
        control_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Стоп")
        self.btn_stop.clicked.connect(self._stop_tracking)
        self.btn_stop.setEnabled(False)
        control_layout.addWidget(self.btn_stop)

        self.tle_label = QLabel("TLE: ожидание загрузки...")
        self.tle_label.setAlignment(Qt.AlignCenter)
        self.tle_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #333; margin-top: 6px;")
        main_layout.addWidget(self.tle_label)

        self.sat_label = QLabel("Спутник: —")
        self.sat_label.setAlignment(Qt.AlignCenter)
        self.sat_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #333; margin-top: 2px;")
        main_layout.addWidget(self.sat_label)

        self.browser = QWebEngineView()
        main_layout.addWidget(self.browser)


    def _load_category(self, category_name: str, force_reload: bool = False) -> None:
        category = self._categories.get(category_name)
        if not category:
            return

        self.tle_label.setText(f"Загрузка данных: {category.name}...")
        QApplication.processEvents()

        try:
            #Load TLE (net or cache)
            self._current_satellites = self._tle_repo.load_category(category, reload=force_reload)
            meta = self._tle_repo.read_meta(category) #read meta

            # статус online/offline + причина
            scr = "ONLINE" if self._tle_repo.last_source == "network" else "OFFLINE (cache)"
            extra = f" | update error: {self._tle_repo.last_error}" if self._tle_repo.last_error else ""

            if meta:
                dt = datetime.fromisoformat(meta.downloaded_at_iso)
                age_sec = (datetime.now(dt.tzinfo) - dt).total_seconds()
                age_min = int(age_sec // 60)

                self.tle_label.setText(
                    f"{scr} | TLE: {age_min} мин назад | источник: {meta.source_url} | спутников: {len(self._current_satellites)}{extra}"
                )
            else:
                self.tle_label.setText(
                    f"{scr} | TLE: нет метаданных | спутников: {len(self._current_satellites)}{extra}"
                )

            #upd combbox
            self.combo_sat.blockSignals(True)
            self.combo_sat.clear()
            self.combo_sat.addItems(self._tle_repo.list_satellite_names(self._current_satellites))
            self.combo_sat.blockSignals(False)

            #selection at start (default)
            self.combo_sat.setCurrentIndex(-1)
            self.sat_label.setText("Выбери сначала епт")
            self._show_placeholder_map()

        except Exception as e:
            traceback.print_exc()  # лог в консоль PyCharm
            self.tle_label.setText(f"Ошибка загрузки TLE: {type(e).__name__}: {e}")
            self.sat_label.setText("Выберите другую категорию или нажмите 'Обновить TLE'")
            self.combo_sat.blockSignals(True)
            self.combo_sat.clear()
            self.combo_sat.blockSignals(False)
            self._show_placeholder_map()
            return

    def _show_placeholder_map(self) -> None:
        from PyQt5.QtCore import QUrl
        import os

        mode = getattr(self._cfg, "placeholder_mode", "folium")

        if mode == "static":
            base_dir = Path(__file__).resolve().parents[2]  # корень проекта (там где папка assets)
            path = base_dir / self._cfg.placeholder_html  # assets/defaultBG.html
            #print("STATIC PLACEHOLDER:", path, "exists:", path.exists()) #отладка
            self.browser.load(QUrl.fromLocalFile(str(path)))
            return

        # режим по-старому: folium генерит временный html
        import folium
        m = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB positron", min_zoom=2)
        folium.Marker(location=[0, 0], popup="Выберите категорию и спутник").add_to(m)

        path = os.path.abspath(self._cfg.placeholder_temp)
        m.save(path)
        self.browser.load(QUrl.fromLocalFile(path))

    def _retry_load_current_category(self) -> None:
        self._load_category(self.combo_category.currentText(), force_reload=True)

    def _update_map(self, sat_name: str) -> None:
        if not sat_name:
            self.sat_label.setText("Выбери сначала епт")
            return

        self._selected_sat_name = sat_name if sat_name else None

        satellite = self._current_satellites.get(sat_name)
        if satellite is None:
            self.sat_label.setText("Спутник не найден в текущей категории")
            return

        # если спутник сменился — сбросить трек, чтобы пересчитать для нового
        if self._track_sat_name != sat_name:
            self._track_sat_name = sat_name
            self._track_segments = None
            self._track_last_update_ts = 0.0

        try:
            state = self._tracker.get_state_now(satellite=satellite, name=sat_name)

            coverage = build_coverage_polygons(
                lat=state.lat_deg,
                lon=state.lon_deg,
                alt_km=state.alt_km,
                earth_radius_km=self._cfg.earth_radius_km,
                min_lat=self._cfg.min_lat,
                max_lat=self._cfg.max_lat,
            )

            self.sat_label.setText(
                f"Спутник: {state.name} | Высота: {state.alt_km:,.0f} км | Радиус покрытия: {coverage.radius_km:,.0f} км"
                f"\n lat={state.lat_deg:.3f} lon={state.lon_deg:.3f}"

            )

            now_ts = time.time()
            need_track = (self._track_segments is None) or (now_ts - self._track_last_update_ts >= 60)

            if need_track:
                if state.alt_km > 30000:
                    minutes_back = 720
                    minutes_forward = 720
                    step_sec = 120
                else:
                    minutes_back = 60
                    minutes_forward = 60
                    step_sec = 60

                points = self._tracker.get_ground_track(
                    satellite=satellite,
                    minutes_back=minutes_back,
                    minutes_forward=minutes_forward,
                    step_sec=step_sec,
                )

                self._track_segments = self._split_track_by_dateline(points)
                self._track_last_update_ts = now_ts

            print("TRACK pts:", len(points), "segments:", [len(s) for s in self._track_segments])

            temp_path = self._renderer.render(
                lat=state.lat_deg,
                lon=state.lon_deg,
                sat_name=state.name,
                polygons=coverage.polygons,
                track_segments=self._track_segments,
            )
            self.browser.load(QUrl.fromLocalFile(temp_path))

        except Exception as e:
            self.sat_label.setText(
                f"Ошибка расчёта/карты: {type(e).__name__}: {e}. Попробуйте другой спутник."
            )

    @staticmethod
    def _split_track_by_dateline(points: List[Tuple[float, float]]) -> List[List[Tuple[float, float]]]:
        if not points:
            return []

        segments = [[points[0]]]
        prev_lon = points[0][1]

        for lat, lon in points[1:]:
            diff = lon - prev_lon

            if diff > 180:
                lon -= 360
            elif diff < -180:
                lon += 360

            if abs(lon - prev_lon) > 180:
                segments.append([])

            segments[-1].append((lat, lon))
            prev_lon = lon

        return [s for s in segments if len(s) > 1]