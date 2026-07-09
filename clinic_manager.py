import sys

def main():
    """Main entry point for the application."""
    # 1. First check if we should run in background server mode (fast path)
    if '--run-django-server' in sys.argv:
        from models.core.server import maybe_run_server_mode
        if maybe_run_server_mode():
            return

    # 2. Otherwise, start the GUI
    # Hide the console window on Windows if running from a script
    from models.utils.os_helpers import hide_console_window
    hide_console_window()

    # 3. Check cached offline login status without loading GUI modules
    from models.utils.auth_helpers import check_offline_login_status
    login_successful, user_data, error_message = check_offline_login_status()

    if not login_successful:
        # Import login window only if login is actually required
        from models.ui.login_window import LoginWindow
        login_app = LoginWindow(error_message=error_message)
        login_app.mainloop()
        login_successful = login_app.login_successful
        user_data = login_app.user_data

    if not login_successful:
        sys.exit(0)

    # 4. Start Main Application Window
    from models.ui.main_window import ClinicManager
    app = ClinicManager(user_data=user_data)
    app.mainloop()

if __name__ == '__main__':
    main()
