import os
import sys
import ctypes
from pathlib import Path
from datetime import datetime

def is_frozen_build():
    return bool(getattr(sys, 'frozen', False))

def get_application_root():
    """
    Detect if running as Nuitka exe or regular Python script.
    Returns the correct root directory for file operations.
    """
    # Check if running as Nuitka compiled exe
    if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
        # PyInstaller-style
        app_root = Path(sys.executable).parent
    elif hasattr(sys, 'frozen'):
        # Nuitka compiled exe
        app_root = Path(sys.executable).parent
    elif '__nuitka_version__' in dir(sys) or '__nuitka__' in dir():
        # Nuitka detection
        app_root = Path(sys.executable).parent
    else:
        # Running as regular Python script
        if __file__.startswith('__nuitka_') or 'nuitka' in __file__.lower():
            # Nuitka-compiled script
            app_root = Path(sys.executable).parent
        else:
            # Regular script
            # Since this is now in models/utils/os_helpers.py, we need to go up two levels from utils
            app_root = Path(__file__).resolve().parent.parent.parent
    
    return app_root

def get_bundle_root():
    if is_frozen_build():
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent.parent

def hide_console_window():
    """Hide the console window on Windows when running script directly."""
    if sys.platform == 'win32':
        try:
            # Get handle to current console window
            kernel32 = ctypes.windll.kernel32
            # SW_HIDE = 0
            kernel32.ShowWindow(kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass  # Silently fail if can't hide console

def log(msg: str, log_file: Path):
    try:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{now}] {msg}\n"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception:
        # Silently fail if logging fails, don't crash the app
        pass

def get_logo_icon_path(app_root: Path):
    # Check bundle root first (for PyInstaller assets)
    try:
        bundle_root = get_bundle_root()
        icon_path = bundle_root / 'logo.ico'
        if icon_path.exists():
            return icon_path
    except Exception:
        pass
        
    # Fallback to application root
    icon_path = app_root / 'logo.ico'
    return icon_path if icon_path.exists() else None

def apply_window_icon(window, app_root: Path):
    icon_path = get_logo_icon_path(app_root)
    if not icon_path:
        return False

    try:
        window.iconbitmap(str(icon_path))
        return True
    except Exception:
        return False

def set_windows_taskbar_icon(window, app_root: Path, app_id: str = 'com.clinic.manager'):
    """Set AppUserModelID and window icons so the taskbar uses the embedded icon."""
    if sys.platform != 'win32':
        return False

    try:
        # Set AppUserModelID for proper taskbar grouping
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

        icon_path = get_logo_icon_path(app_root)
        if not icon_path:
            return False

        # Ensure the window has been realized so we can get a valid HWND
        try:
            window.update_idletasks()
            hwnd = window.winfo_id()
        except Exception:
            return False

        # Load the icon from file and set both small and big icons
        LR_LOADFROMFILE = 0x00000010
        IMAGE_ICON = 1
        LoadImageW = ctypes.windll.user32.LoadImageW
        handle = LoadImageW(None, str(icon_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
        if not handle:
            return False

        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, handle)
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, handle)
        return True
    except Exception:
        return False
