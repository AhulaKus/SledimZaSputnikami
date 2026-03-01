from __future__ import annotations

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

        self.info_label = QLabel("Ожидание загрузки данных...")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333; margin-top: 5px;")
        main_layout.addWidget(self.info_label)

        self.browser = QWebEngineView()
        main_layout.addWidget(self.browser)

    def _load_category(self, category_name: str) -> None:
        category = self._categories.get(category_name)
        if not category:
            return

        self.info_label.setText(f"Загрузка данных: {category.name}...")
        QApplication.processEvents()

        try:
            self._current_satellites = self._tle_repo.load_category(category, reload=False)


            self.combo_sat.blockSignals(True)
            self.combo_sat.clear()
            self.combo_sat.addItems(self._tle_repo.list_satellite_names(self._current_satellites))
            self.combo_sat.blockSignals(False)

            if self.combo_sat.count() > 0:
                self.combo_sat.setCurrentIndex(0)
                self._update_map(self.combo_sat.currentText())


        except Exception as e:
            traceback.print_exc()
            self.info_label.setText(f"Ошибка загрузки данных: {type(e).__name__}: {e}")

    def _update_map(self, sat_name: str) -> None:
        if not sat_name:
            return
        satellite = self._current_satellites.get(sat_name)
        if satellite is None:
            return

        state = self._tracker.get_state_now(satellite=satellite, name=sat_name)

        coverage = build_coverage_polygons(
            lat=state.lat_deg,
            lon=state.lon_deg,
            alt_km=state.alt_km,
            earth_radius_km=self._cfg.earth_radius_km,
            min_lat=self._cfg.min_lat,
            max_lat=self._cfg.max_lat,
        )

        self.info_label.setText(
            f"Спутник: {state.name}   |   Высота: {state.alt_km:,.0f} км   |   Радиус покрытия: {coverage.radius_km:,.0f} км"
        )

        temp_path = self._renderer.render(
            lat=state.lat_deg,
            lon=state.lon_deg,
            sat_name=state.name,
            polygons=coverage.polygons,
        )
        self.browser.load(QUrl.fromLocalFile(temp_path))