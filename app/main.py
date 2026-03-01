import sys

from PyQt5.QtWidgets import QApplication

from app.config import AppConfig
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(AppConfig())
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())