import sys
from models.core.server import maybe_run_server_mode
from models.utils.os_helpers import hide_console_window

def main():
    """Main entry point for the application."""
    # 1. First check if we should run in background server mode
    if maybe_run_server_mode():
        return

    # 2. Otherwise, start the GUI
    # Hide the console window on Windows if running from a script
    hide_console_window()

    # Import UI here to keep server mode lightweight
    from models.ui.main_window import ClinicManager
    
    app = ClinicManager()
    app.mainloop()

if __name__ == '__main__':
    main()
