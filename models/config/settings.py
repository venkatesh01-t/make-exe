from pathlib import Path
from models.utils.os_helpers import get_application_root, is_frozen_build, get_bundle_root

# Configuration - automatically adapt to exe or script location
APP_ROOT = get_application_root()
DATA_SUBFOLDER = APP_ROOT / 'clinic_manager_data'
WORKSPACE = DATA_SUBFOLDER  # All downloads/clinic go here
PYTHON_EXE = WORKSPACE / '3.11.9' / 'python.exe'
LOG_FILE = WORKSPACE / 'manager.log'
AUTH_FILE = WORKSPACE / 'login_data.enc'

def get_project_dir():
    if is_frozen_build():
        return get_bundle_root() / 'clinic'
    return WORKSPACE / 'clinic'

def get_runtime_data_dir():
    return WORKSPACE / 'data'

def get_runtime_static_dir():
    if is_frozen_build():
        return get_bundle_root() / 'staticfiles'
    return WORKSPACE / 'staticfiles'

PROJECT_DIR = get_project_dir()
DATA_DIR = get_runtime_data_dir()

# Theme and font constants for easier styling
THEME = {
    'dark_bg': '#2c3e50',
    'light_bg': '#f0f0f0',
    'accent': '#3498db',
    'muted': '#7f8c8d',
    'footer_bg': '#ecf0f1',
    'canvas_border': '#bdc3c7',
}

FONTS = {
    'title': ('Segoe UI', 24, 'bold'),
    'subtitle': ('Segoe UI', 11),
    'logo': ('Segoe UI', 16, 'bold'),
    'label_bold': ('Segoe UI', 10, 'bold'),
    'small': ('Segoe UI', 9),
    'mono': ('Consolas', 9),
}

# Login settings
LOGIN_API_URL = "https://login-api-qduo.vercel.app/api/login/"
SECRET_KEY = b'aV3JE9Z0ef3x1pP1nv_zal7ZPID4LOvD1441rdYVnRc='

