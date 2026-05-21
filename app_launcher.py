
from path_manager import get_app_paths
from logger import setup_logger, get_logger
from logger import get_logger

logger = get_logger('launcher')


class AppLauncher:
    def __init__(self):
        self.paths = get_app_paths()
        self.django_server = None

    def bootstrap(self):
        logger.info("Bootstrap process started")
        return True, "http://127.0.0.1:8000"

    def shutdown(self):
        logger.info("Shutting down")


def launch_application():
    launcher = AppLauncher()
    return launcher.bootstrap()
