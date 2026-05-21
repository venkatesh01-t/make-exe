"""Path management and resolution for Clinic Desktop Application."""

import sys
from pathlib import Path


def get_base_path() -> Path:
    """Detect application root directory based on execution context."""
    if hasattr(sys, '__nuitka_version__'):
        return Path(sys.executable).parent
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    if hasattr(sys, 'frozen'):
        return Path(sys.executable).parent
    if hasattr(sys, '__file__'):
        return Path(sys.__file__).resolve().parent
    return Path.cwd()


class AppPaths:
    """Central repository for all application paths."""

    def __init__(self):
        self.base_path = get_base_path()
        self._create_directories()

    def _create_directories(self):
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)
        self.media_path.mkdir(parents=True, exist_ok=True)
        self.runtime_cache_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)

    @property
    def base_path(self) -> Path:
        return self._base_path

    @base_path.setter
    def base_path(self, value: Path):
        self._base_path = Path(value)

    @property
    def python_path(self) -> Path:
        return self.base_path / "python" / "python.exe"

    @property
    def django_path(self) -> Path:
        return self.base_path / "clinic"

    @property
    def data_path(self) -> Path:
        return self.base_path / "Data"

    @property
    def db_path(self) -> Path:
        return self.data_path / "db.sqlite3"

    @property
    def media_path(self) -> Path:
        return self.data_path / "media"

    @property
    def logs_path(self) -> Path:
        return self.data_path / "logs"

    @property
    def static_path(self) -> Path:
        return self.data_path / "static"

    @property
    def runtime_cache_path(self) -> Path:
        return self.base_path / "runtime"

    @property
    def temp_path(self) -> Path:
        return self.base_path / "temp"

    @property
    def config_file(self) -> Path:
        return self.data_path / "config.json"

    @property
    def env_lock_file(self) -> Path:
        return self.data_path / "clinic_env_lock.json"

    @property
    def version_file(self) -> Path:
        return self.data_path / "clinic_version.txt"

    @property
    def update_cache_path(self) -> Path:
        return self.temp_path / "clinic_update.exe"

    def is_running_as_exe(self) -> bool:
        return hasattr(sys, 'frozen') or hasattr(sys, '__nuitka_version__')

    def ensure_all_paths_exist(self):
        self._create_directories()


_app_paths = None


def get_app_paths() -> AppPaths:
    global _app_paths
    if _app_paths is None:
        _app_paths = AppPaths()
    return _app_paths
