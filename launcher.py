
import sys
import os

def hide_console_window():
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                kernel32.ShowWindow(hwnd, 0)
        except:
            pass

hide_console_window()

from path_manager import get_app_paths
from logger import setup_logger, get_logger
from app_launcher import launch_application
from gui_main import ClinicDesktopApp, show_error_dialog

from PySide6.QtWidgets import QApplication

logger = None

def main():
    global logger
    
    paths = get_app_paths()
    logger = setup_logger(paths.logs_path)
    
    logger.info("Clinic Desktop Application starting...")
    
    try:
        qt_app = QApplication(sys.argv)
        main_window = ClinicDesktopApp()
        
        main_window.show_splash_screen()
        success, server_url = launch_application()
        main_window.close_splash()
        
        if success:
            main_window.server_url = server_url
            main_window.load_django_app()
            main_window.show()
            exit_code = qt_app.exec()
        else:
            main_window.show_error("Error", "Bootstrap failed")
            exit_code = 1
        
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
