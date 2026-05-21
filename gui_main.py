
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QIcon, QPixmap, QColor
from logger import get_logger

logger = get_logger('gui')


class ClinicDesktopApp(QMainWindow):
    def __init__(self, server_url: str = "http://127.0.0.1:8000"):
        super().__init__()
        self.server_url = server_url
        self.django_server = None
        self.setWindowTitle("Clinic Management System")
        self.setMinimumSize(1000, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        logger.info("GUI initialized")

    def load_django_app(self):
        logger.info(f"Loading: {self.server_url}")

    def show_error(self, title: str, message: str):
        logger.error(f"{title}: {message}")

    def show_splash_screen(self):
        pass

    def update_splash(self, message: str, progress: int):
        pass

    def close_splash(self):
        pass


def show_error_dialog(title: str, message: str, details: str = ""):
    logger.error(f"{title}: {message}")
