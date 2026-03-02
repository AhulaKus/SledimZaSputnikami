from __future__ import annotations

from datetime import datetime

from typing import Dict

from PyQt5.QtCore import QUrl, Qt
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

        # --- 1) Строка про актуальность TLE (чтобы не перетиралась) ---
        self.tle_label = QLabel("TLE: ожидание загрузки...")
        self.tle_label.setAlignment(Qt.AlignCenter)
        self.tle_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #333; margin-top: 6px;")
        main_layout.addWidget(self.tle_label)

        # --- 2) Строка про выбранный спутник ---
        self.sat_label = QLabel("Спутник: —")
        self.sat_label.setAlignment(Qt.AlignCenter)
        self.sat_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #333; margin-top: 2px;")
        main_layout.addWidget(self.sat_label)

        self.browser = QWebEngineView()
        main_layout.addWidget(self.browser)

        self.last_source = "unknown" #online/offline

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

            scr = "ONLINE" if getattr(self._tle_repo, "last_source", "") == "network" else "OFFLINE (cache)"
            if meta:
                dt = datetime.fromisoformat(meta.downloaded_at_iso)
                age_sec = (datetime.now(dt.tzinfo) - dt).total_seconds()
                age_min = int(age_sec // 60)
                self.tle_label.setText(
                    f"{scr} | TLE: {age_min} мин назад | источник: {meta.source_url} | спутников: {len(self._current_satellites)}"
                )
            else:
                self.tle_label.setText(
                    f"{scr} | TLE: нет метаданных | спутников: {len(self._current_satellites)}"
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
            traceback.print_exc()
            self.tle_label.setText(f"Ошибка загрузки данных: {type(e).__name__}: {e}")
            raise #

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

        satellite = self._current_satellites.get(sat_name)
        if satellite is None:
            self.sat_label.setText("Спутник не найден в текущей категории")
            return

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
            )

            temp_path = self._renderer.render(
                lat=state.lat_deg,
                lon=state.lon_deg,
                sat_name=state.name,
                polygons=coverage.polygons,
            )
            self.browser.load(QUrl.fromLocalFile(temp_path))

        except Exception as e:
            self.set_label.setText(f"Ошибка расчетов/карты: {type(e).__name__}: {e}")
