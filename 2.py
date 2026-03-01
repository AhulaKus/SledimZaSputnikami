import sys
import os
import math
import folium
from skyfield.api import load

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QComboBox, QLabel, QPushButton)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, Qt


class SatelliteTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("МТУСИ: Сферическая картография (Без разрывов)")
        self.resize(1200, 850)

        # Ссылки на TLE
        self.categories = {
            "GPS (Навигация)": "https://celestrak.org/NORAD/elements/gps-ops.txt",
            "Космические станции (МКС)": "https://celestrak.org/NORAD/elements/stations.txt",
            "Метеоспутники (Weather)": "https://celestrak.org/NORAD/elements/weather.txt",
            "ГЛОНАСС (Навигация)": "https://celestrak.org/NORAD/elements/glo-ops.txt",
            "Спутники связи (Molniya)": "https://celestrak.org/NORAD/elements/molniya.txt",
            "Геостационарные (ТВ)": "https://celestrak.org/NORAD/elements/geo.txt",
            "Starlink": "https://celestrak.org/NORAD/elements/starlink.txt"
        }

        self.current_satellites = {}

        # --- ИНТЕРФЕЙС ---
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
        self.combo_category.addItems(self.categories.keys())
        self.combo_category.currentTextChanged.connect(self.load_category_data)
        control_layout.addWidget(self.combo_category, stretch=1)

        control_layout.addWidget(QLabel("2. Спутник:"))
        self.combo_sat = QComboBox()
        self.combo_sat.currentTextChanged.connect(self.update_map)
        control_layout.addWidget(self.combo_sat, stretch=1)

        btn_exit = QPushButton("Выход")
        btn_exit.setStyleSheet(
            "background-color: #d32f2f; color: white; border-radius: 3px; font-weight: bold; padding: 5px 15px;")
        btn_exit.clicked.connect(self.close)
        control_layout.addWidget(btn_exit)

        main_layout.addWidget(control_panel)

        # Информационная строка
        self.info_label = QLabel("Ожидание загрузки данных...")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333; margin-top: 5px;")
        main_layout.addWidget(self.info_label)

        self.browser = QWebEngineView()
        main_layout.addWidget(self.browser)

        self.load_category_data(self.combo_category.currentText())

    def load_category_data(self, category_name):
        url = self.categories.get(category_name)
        if not url: return
        self.info_label.setText(f"Загрузка данных: {category_name}...")
        QApplication.processEvents()
        try:
            sat_list = load.tle_file(url, reload=False)
            self.current_satellites = {sat.name: sat for sat in sat_list}
            self.combo_sat.blockSignals(True)
            self.combo_sat.clear()
            self.combo_sat.addItems(sorted(self.current_satellites.keys()))
            self.combo_sat.blockSignals(False)
            if self.combo_sat.count() > 0:
                self.combo_sat.setCurrentIndex(0)
                self.update_map(self.combo_sat.currentText())
        except Exception as e:
            self.info_label.setText("Ошибка загрузки данных. Попробуйте другую категорию.")

    # --- ИСПРАВЛЕННОЕ МАТЕМАТИЧЕСКОЕ ЯДРО ---
    def get_lat_for_lon(self, lat_center_deg, dlon_deg, angular_radius_rad):
        """Аналитическое решение с защитой от 'мертвых зон' на обратной стороне Земли"""
        lat1 = math.radians(lat_center_deg)
        dlon = math.radians(dlon_deg)
        C = math.cos(angular_radius_rad)
        A = math.sin(lat1)
        B = math.cos(lat1) * math.cos(dlon)

        R_eq = math.sqrt(A ** 2 + B ** 2)
        if R_eq == 0:
            return []

        ratio = C / R_eq
        # Защита от погрешности вычислений
        ratio = max(-1.0, min(1.0, ratio))

        alpha = math.atan2(B, A)
        val1 = math.asin(ratio)
        val2 = math.pi - val1

        lat2_1 = math.degrees(val1 - alpha)
        lat2_2 = math.degrees(val2 - alpha)

        # ГЛАВНЫЙ ФИКС: Нормализуем углы к стандартному диапазону[-180, 180]
        # Это позволяет правильно считать дугу, перевалившую через полюс
        lat2_1 = (lat2_1 + 180) % 360 - 180
        lat2_2 = (lat2_2 + 180) % 360 - 180

        valid_lats = []
        if -90 <= lat2_1 <= 90: valid_lats.append(lat2_1)
        if -90 <= lat2_2 <= 90: valid_lats.append(lat2_2)

        return valid_lats

    def get_continuous_circle(self, lat, lon, radius_km):
        coords = []
        R = 6371.0
        lat1, lon1 = math.radians(lat), math.radians(lon)
        d = radius_km / R

        brng = 0
        lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brng))
        lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(d) * math.cos(lat1),
                                 math.cos(d) - math.sin(lat1) * math.sin(lat2))

        prev_lon = math.degrees(lon2)
        while prev_lon - lon < -180: prev_lon += 360
        while prev_lon - lon > 180: prev_lon -= 360
        coords.append([max(-85.0, min(85.0, math.degrees(lat2))), prev_lon])

        for brng_deg in range(2, 361, 2):
            brng = math.radians(brng_deg)
            lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brng))
            lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(d) * math.cos(lat1),
                                     math.cos(d) - math.sin(lat1) * math.sin(lat2))

            curr_lon = math.degrees(lon2)
            while curr_lon - prev_lon < -180: curr_lon += 360
            while curr_lon - prev_lon > 180: curr_lon -= 360

            coords.append([max(-85.0, min(85.0, math.degrees(lat2))), curr_lon])
            prev_lon = curr_lon

        return coords

    def update_map(self, sat_name):
        if not sat_name or sat_name not in self.current_satellites: return
        satellite = self.current_satellites[sat_name]
        t = load.timescale().now()

        geocentric = satellite.at(t)
        subpoint = geocentric.subpoint()
        lat = subpoint.latitude.degrees
        lon = subpoint.longitude.degrees
        alt_km = subpoint.elevation.m / 1000.0

        R_EARTH = 6371.0
        radius_km = 0
        d_rad = 0
        if alt_km > 0:
            val = R_EARTH / (R_EARTH + alt_km)
            if val > 1: val = 1
            d_rad = math.acos(val)
            radius_km = d_rad * R_EARTH

        self.info_label.setText(
            f"Спутник: {sat_name}   |   Высота: {alt_km:,.0f} км   |   Радиус покрытия: {radius_km:,.0f} км")

        m = folium.Map(location=[lat, lon], zoom_start=2, tiles='CartoDB positron', min_zoom=2)

        folium.Marker(
            location=[lat, lon],
            popup=f"<b>{sat_name}</b>",
            icon=folium.Icon(color="red", icon="rocket", prefix='fa')
        ).add_to(m)

        if radius_km > 10:
            dist_to_north_rad = math.radians(90.0 - lat)
            dist_to_south_rad = math.radians(lat - (-90.0))

            covers_north = d_rad >= dist_to_north_rad
            covers_south = d_rad >= dist_to_south_rad

            polygons_to_draw = []

            MAX_LAT = 85.0
            MIN_LAT = -85.0

            if covers_north and covers_south:
                # Накрывает всю Землю
                coords = []
                for lon_deg in range(-180, 181, 5): coords.append([MAX_LAT, float(lon_deg)])
                for lon_deg in range(180, -181, -5): coords.append([MIN_LAT, float(lon_deg)])
                polygons_to_draw.append(coords)

            elif covers_north:
                # Накрывает только Северный полюс
                coords = []
                # Идем по нижней дуге
                for lon_deg in range(-180, 181, 2):
                    lats = self.get_lat_for_lon(lat, lon_deg - lon, d_rad)
                    bound_lat = min(lats) if lats else MIN_LAT
                    bound_lat = max(MIN_LAT, min(MAX_LAT, bound_lat))
                    coords.append([bound_lat, float(lon_deg)])
                # Идем по верху карты обратно
                for lon_deg in range(180, -181, -2):
                    coords.append([MAX_LAT, float(lon_deg)])
                polygons_to_draw.append(coords)

            elif covers_south:
                # Накрывает только Южный полюс (GPS BIIF-10 из твоего примера)
                coords = []
                # Идем по верхней дуге
                for lon_deg in range(-180, 181, 2):
                    lats = self.get_lat_for_lon(lat, lon_deg - lon, d_rad)
                    bound_lat = max(lats) if lats else MAX_LAT
                    bound_lat = max(MIN_LAT, min(MAX_LAT, bound_lat))
                    coords.append([bound_lat, float(lon_deg)])
                # Идем по низу карты обратно
                for lon_deg in range(180, -181, -2):
                    coords.append([MIN_LAT, float(lon_deg)])
                polygons_to_draw.append(coords)

            else:
                # Обычный круг
                coords = self.get_continuous_circle(lat, lon, radius_km)
                polygons_to_draw.append(coords)

                lons = [pt[1] for pt in coords]
                if max(lons) > 180:
                    polygons_to_draw.append([[pt[0], pt[1] - 360] for pt in coords])
                if min(lons) < -180:
                    polygons_to_draw.append([[pt[0], pt[1] + 360] for pt in coords])

            # Рисуем
            for poly in polygons_to_draw:
                folium.Polygon(
                    locations=poly,
                    color="blue",
                    weight=2,
                    fill=True,
                    fill_color="blue",
                    fill_opacity=0.25
                ).add_to(m)

        temp_file = os.path.abspath("temp_map_final.html")
        m.save(temp_file)
        self.browser.load(QUrl.fromLocalFile(temp_file))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SatelliteTrackerApp()
    window.show()
    sys.exit(app.exec_())