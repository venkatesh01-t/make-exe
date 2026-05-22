import os
import sys
import threading
import zipfile
import shutil
import subprocess
import socket
import time
import queue
from datetime import datetime
from pathlib import Path
from datetime import timedelta

# Always import tkinter base
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Try to import customtkinter for modern UI
try:
    import customtkinter as ctk
except ImportError:
    # Fallback to standard tkinter if customtkinter not available
    ctk = None

try:
    import requests
except Exception:
    requests = None

try:
    import qrcode
except Exception:
    qrcode = None


# ============================================================================
# HIDE CONSOLE WINDOW (Windows only)
# ============================================================================
def hide_console_window():
    """Hide the console window on Windows when running script directly."""
    if sys.platform == 'win32':
        try:
            import ctypes
            # Get handle to current console window
            kernel32 = ctypes.windll.kernel32
            # SW_HIDE = 0
            kernel32.ShowWindow(kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass  # Silently fail if can't hide console

# Hide console window immediately on startup
hide_console_window()


# ============================================================================
# NUITKA COMPILATION DETECTION & PATH CONFIGURATION
# ============================================================================
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
            app_root = Path(__file__).resolve().parent
    
    return app_root


def get_bundle_root():
    if is_frozen_build():
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).resolve().parent


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


def get_server_command(port: int):
    manage_py = str(PROJECT_DIR / 'manage.py')
    if is_frozen_build():
        if PYTHON_EXE.exists() and Path(manage_py).exists():
            return [str(PYTHON_EXE), manage_py, 'runserver', f'0.0.0.0:{port}']
        return [str(sys.executable), '--run-django-server', str(port)]
    return [str(PYTHON_EXE), manage_py, 'runserver', f'0.0.0.0:{port}']


def run_embedded_django_server(port: int):
    project_dir = get_project_dir()
    if not project_dir.exists():
        raise FileNotFoundError(f'Bundled clinic project not found at {project_dir}')

    runtime_data_dir = get_runtime_data_dir()
    runtime_static_dir = get_runtime_static_dir()
    runtime_data_dir.mkdir(parents=True, exist_ok=True)
    runtime_static_dir.mkdir(parents=True, exist_ok=True)

    project_parent = str(project_dir.parent)
    project_path = str(project_dir)
    if project_parent not in sys.path:
        sys.path.insert(0, project_parent)
    if project_path not in sys.path:
        sys.path.insert(0, project_path)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clinic.settings')
    os.environ.setdefault('CLINIC_DATA_DIR', str(runtime_data_dir))
    os.environ.setdefault('CLINIC_STATIC_ROOT', str(runtime_static_dir))

    if PYTHON_EXE.exists():
        os.execv(str(PYTHON_EXE), [str(PYTHON_EXE), str(project_dir / 'manage.py'), 'runserver', f'0.0.0.0:{port}'])

    from django.core.management import execute_from_command_line

    execute_from_command_line([sys.argv[0], 'runserver', f'0.0.0.0:{port}'])


def maybe_run_server_mode():
    if '--run-django-server' not in sys.argv:
        return False

    try:
        arg_index = sys.argv.index('--run-django-server')
        port = int(sys.argv[arg_index + 1]) if len(sys.argv) > arg_index + 1 else 8000
    except Exception:
        port = 8000

    run_embedded_django_server(port)
    return True

# Configuration - automatically adapt to exe or script location
APP_ROOT = get_application_root()
DATA_SUBFOLDER = APP_ROOT / 'clinic_manager_data'
WORKSPACE = DATA_SUBFOLDER  # All downloads/clinic go here
PYTHON_EXE = WORKSPACE / '3.11.9' / 'python.exe'
PROJECT_DIR = get_project_dir()
DATA_DIR = get_runtime_data_dir()
LOG_FILE = WORKSPACE / 'manager.log'

# Note: Nuitka compiles Python code to C, so bundled Python is handled via Nuitka compilation
# The exe includes all dependencies needed for package installation and server execution
# Use: python -m nuitka --onefile --windows-subsystem=gui clinic_manager.py

def log(msg: str):
    try:
        # Ensure log directory exists
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{now}] {msg}\n"
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        # Silently fail if logging fails, don't crash the app
        pass


class ClinicManager(ctk.CTk if ctk else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Clinic Manager')
        self.geometry('900x600')
        if ctk:
            ctk.set_appearance_mode('dark')
        else:
            self.configure(bg='#f0f0f0')
        
        # Initialize variables first before creating splash screen
        self.url_var = tk.StringVar(value='')
        self.port_var = tk.IntVar(value=8000)
        self.progress_var = tk.DoubleVar(value=0)
        self.server_process = None
        self.server_running = False
        self.output_queue = queue.Queue()
        self.server_port = 8000  # Track the actual port being used
        self.current_ip = None  # Track current IP address
        self.network_monitor_running = False  # Network monitoring flag
        self.last_ip_check_time = 0  # Rate limiting for IP checks
        
        # Set up window close handler for proper cleanup
        self.protocol('WM_DELETE_WINDOW', self.on_closing)
        
        # Hide main window initially
        self.withdraw()
        
        # Create splash screen with classic design
        self.splash = tk.Toplevel(self)
        self.splash.title('Clinic Manager')
        self.splash.geometry('500x350')
        self.splash.resizable(False, False)
        self.splash.configure(bg='#f0f0f0')
        
        # Center splash screen on screen
        self.splash.update_idletasks()
        x = (self.splash.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.splash.winfo_screenheight() // 2) - (350 // 2)
        self.splash.geometry(f'500x350+{x}+{y}')
        
        # Splash header frame (classic style)
        header_frame = tk.Frame(self.splash, bg='#2c3e50', height=80)
        header_frame.pack(side='top', fill='x')
        header_frame.pack_propagate(False)
        
        # Title in header
        title_label = tk.Label(header_frame, text='Clinic Manager', font=('Segoe UI', 24, 'bold'), 
                              bg='#2c3e50', fg='white')
        title_label.pack(pady=15)
        
        # Version label
        version_label = tk.Label(header_frame, text='v1.0 - Healthcare System', font=('Segoe UI', 9), 
                                bg='#2c3e50', fg='#ecf0f1')
        version_label.pack()
        
        # Content frame
        content_frame = tk.Frame(self.splash, bg='#f0f0f0')
        content_frame.pack(side='top', fill='both', expand=True, padx=40, pady=30)
        
        # Status message
        self.splash_label = tk.Label(content_frame, text='Initializing system...\nPlease wait', 
                                     font=('Segoe UI', 11), bg='#f0f0f0', fg='#2c3e50', justify='center')
        self.splash_label.pack(pady=15)
        
        # Progress bar on splash (indeterminate style)
        progress_frame = tk.Frame(content_frame, bg='#f0f0f0')
        progress_frame.pack(fill='x', pady=15)
        
        self.splash_progress = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                               maximum=100, length=350, mode='determinate')
        self.splash_progress.pack(fill='x')
        
        # Progress label
        self.splash_status = tk.Label(content_frame, text='0%', font=('Segoe UI', 9), 
                                      bg='#f0f0f0', fg='#7f8c8d')
        self.splash_status.pack(pady=5)
        
        # Footer frame
        footer_frame = tk.Frame(self.splash, bg='#ecf0f1', height=40)
        footer_frame.pack(side='bottom', fill='x')
        footer_frame.pack_propagate(False)
        
        footer_label = tk.Label(footer_frame, text='Loading system components...', 
                               font=('Segoe UI', 8), bg='#ecf0f1', fg='#7f8c8d')
        footer_label.pack(pady=10)
        
        self.splash.update()

        # Top control frame with enhanced classic styling
        top = ctk.CTkFrame(self) if ctk else tk.Frame(self, bg='#2c3e50', border=1, relief='solid')
        top.pack(side='top', fill='x', padx=0, pady=0)

        # Create a button style helper for classic design
        button_font = ('Segoe UI', 10, 'bold')
        button_bg = '#3498db'
        button_fg = 'white'
        button_activebg = '#2980b9'
        button_disablebg = '#95a5a6'

        if ctk:
            ctk.CTkButton(top, text='Start Server', command=self.threaded(self.start_server)).pack(side='left', padx=8, pady=12)
            ctk.CTkButton(top, text='Stop Server', command=self.stop_server).pack(side='left', padx=8, pady=12)
            ctk.CTkButton(top, text='Open Browser', command=self.open_browser).pack(side='left', padx=8, pady=12)
            ctk.CTkButton(top, text='Backup Data', command=self.threaded(self.backup_data)).pack(side='right', padx=8, pady=12)
            ctk.CTkButton(top, text='Restore Data', command=self.threaded(self.restore_data)).pack(side='right', padx=8, pady=12)
        else:
            btn_style = {'font': button_font, 'bg': button_bg, 'fg': button_fg, 
                        'activebackground': button_activebg, 'activeforeground': button_fg,
                        'relief': 'solid', 'border': 0, 'padx': 12, 'pady': 8,
                        'cursor': 'hand2'}
            
            self.start_btn = tk.Button(top, text='Start Server', command=self.threaded(self.start_server), **btn_style)
            self.start_btn.pack(side='left', padx=8, pady=12)
            self.stop_btn = tk.Button(top, text='Stop Server', command=self.stop_server, **btn_style)
            self.stop_btn.pack(side='left', padx=8, pady=12)
            self.stop_btn.config(state='disabled')
            self.browser_btn = tk.Button(top, text='Open Browser', command=self.open_browser, **btn_style)
            self.browser_btn.pack(side='left', padx=8, pady=12)
            self.browser_btn.config(state='disabled')
            tk.Button(top, text='Backup Data', command=self.threaded(self.backup_data), **btn_style).pack(side='right', padx=8, pady=12)
            tk.Button(top, text='Restore Data', command=self.threaded(self.restore_data), **btn_style).pack(side='right', padx=8, pady=12)

        # URL and QR frame with enhanced classic styling
        mid = ctk.CTkFrame(self) if ctk else tk.Frame(self, bg='#ecf0f1', border=1, relief='solid')
        mid.pack(side='top', fill='x', padx=12, pady=8)

        if ctk:
            ctk.CTkLabel(mid, text='Server URL:', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=8, pady=8)
            ctk.CTkLabel(mid, textvariable=self.url_var, text_color='#3498db', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=8, pady=8)
        else:
            url_title = tk.Label(mid, text='Server URL:', font=('Segoe UI', 10, 'bold'), bg='#ecf0f1', fg='#2c3e50')
            url_title.pack(side='left', padx=8, pady=8)
            url_label = tk.Label(mid, textvariable=self.url_var, font=('Segoe UI', 10, 'bold'), bg='#ecf0f1', fg='#3498db')
            url_label.pack(side='left', padx=8, pady=8)

        # Canvas for QR code - always use white background for visibility
        self.qr_canvas = tk.Canvas(mid, width=200, height=200, bg='white', highlightthickness=2, highlightbackground='#bdc3c7')
        self.qr_canvas.pack(side='right', padx=12)

        # Access Methods Panel - Beautiful display of all connection options
        access_frame = ctk.CTkFrame(self) if ctk else tk.Frame(self, bg='#2c3e50', border=1, relief='solid')
        access_frame.pack(side='top', fill='x', padx=12, pady=8)
        
        # Header for access methods
        header_frame = tk.Frame(access_frame, bg='#2c3e50')
        header_frame.pack(fill='x', padx=12, pady=8)
        header_label = tk.Label(header_frame, text='📱 Network Access Methods', font=('Segoe UI', 10, 'bold'), bg='#2c3e50', fg='white')
        header_label.pack(anchor='w')
        
        # Content frame with two columns
        content_frame = tk.Frame(access_frame, bg='#2c3e50')
        content_frame.pack(fill='both', expand=True, padx=12, pady=8)
        
        # Left column - Same Computer
        left_col = tk.Frame(content_frame, bg='#2c3e50')
        left_col.pack(side='left', fill='both', expand=True, padx=(0, 15))
        
        left_header = tk.Label(left_col, text='🖥️  Same Computer:', font=('Segoe UI', 9, 'bold'), bg='#2c3e50', fg='#3498db')
        left_header.pack(anchor='w', pady=(0, 5))
        
        self.localhost_label = tk.Label(left_col, text='🔗 http://localhost:8000', font=('Segoe UI', 10), bg='#2c3e50', fg='#ecf0f1', wraplength=200, justify='left')
        self.localhost_label.pack(anchor='w', pady=2)
        
        self.loopback_label = tk.Label(left_col, text='🔗 http://127.0.0.1:8000', font=('Segoe UI', 10), bg='#2c3e50', fg='#ecf0f1', wraplength=200, justify='left')
        self.loopback_label.pack(anchor='w', pady=2)
        
        # Right column - Other Devices
        right_col = tk.Frame(content_frame, bg='#2c3e50')
        right_col.pack(side='left', fill='both', expand=True, padx=(15, 0))
        
        right_header = tk.Label(right_col, text='📱 Other Devices (Same WiFi):', font=('Segoe UI', 9, 'bold'), bg='#2c3e50', fg='#3498db')
        right_header.pack(anchor='w', pady=(0, 5))
        
        self.ip_label = tk.Label(right_col, text='🔗 http://192.168.1.100:8000', font=('Segoe UI', 10), bg='#2c3e50', fg='#ecf0f1', wraplength=200, justify='left')
        self.ip_label.pack(anchor='w', pady=2)
        
        self.hostname_label = tk.Label(right_col, text='🔗 http://DESKTOP-NAME:8000', font=('Segoe UI', 10), bg='#2c3e50', fg='#ecf0f1', wraplength=250, justify='left')
        self.hostname_label.pack(anchor='w', pady=2)

        # Progress info frame with progress bar - enhanced classic design
        progress_container = ctk.CTkFrame(self) if ctk else tk.Frame(self, bg='#f0f0f0')
        progress_container.pack(side='top', fill='x', padx=12, pady=10)
        
        # Progress bar frame with border
        progress_frame = ctk.CTkFrame(self) if ctk else tk.Frame(self, bg='white', border=1, relief='solid')
        progress_frame.pack(in_=progress_container, fill='x', padx=0, pady=0)
        
        # Progress bar for downloads - styled with better appearance
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=400, mode='determinate')
        self.progress_bar.pack(fill='x', padx=8, pady=8)


        # Output area with enhanced classic styling
        bottom = ctk.CTkFrame(self) if ctk else tk.Frame(self, bg='#f0f0f0')
        bottom.pack(side='top', fill='both', expand=True, padx=12, pady=12)
        
        # Output header frame
        output_header = tk.Frame(bottom, bg='#f0f0f0')
        output_header.pack(fill='x', pady=(0, 8))
        
        # Output label with better styling
        output_label = tk.Label(output_header, text='System Output Log', font=('Segoe UI', 10, 'bold'), bg='#f0f0f0', fg='#2c3e50')
        output_label.pack(anchor='w')

        # Output text frame with border
        output_frame = tk.Frame(bottom, bg='white', border=1, relief='solid')
        output_frame.pack(fill='both', expand=True)
        
        self.output = tk.Text(output_frame, height=20, wrap='word', bg='white', fg='#2c3e50', 
                            font=('Consolas', 9), border=0, relief='flat',
                            highlightthickness=0)
        self.output.pack(fill='both', expand=True, padx=1, pady=1)
        
        # Add scrollbar to output
        scrollbar = ttk.Scrollbar(output_frame, command=self.output.yview)
        scrollbar.pack(side='right', fill='y')
        self.output.config(yscrollcommand=scrollbar.set)

        self.after(100, self.process_output_queue)

        # Ensure workspace directory exists
        try:
            WORKSPACE.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            pass  # Will be caught during startup checks

        threading.Thread(target=self.startup_checks, daemon=True).start()

    def threaded(self, fn):
        def wrapper(*a, **k):
            t = threading.Thread(target=fn, args=a, kwargs=k, daemon=True)
            t.start()
        return wrapper

    def append_output(self, text: str):
        self.output_queue.put(text)

    def process_output_queue(self):
        try:
            while True:
                text = self.output_queue.get_nowait()
                self.output.insert('end', text + '\n')
                self.output.see('end')
                log(text)
        except queue.Empty:
            pass
        self.after(100, self.process_output_queue)

    def update_progress(self, value):
        self.progress_var.set(value)
    
    def reset_progress(self):
        self.progress_var.set(0)

    def startup_checks(self):
        """Run startup checks: download repo, check folders, install requirements."""
        try:
            self.append_output('=== STARTUP CHECKS STARTED ===')
            self.append_output(f'Application Root: {APP_ROOT}')
            self.append_output(f'Working Directory: {WORKSPACE}')
            self.append_output(f'Python Executable: {PYTHON_EXE}')
            self.ensure_runtime_directories()

            required_items = self.get_required_setup_items()
            missing_items = [str(path) for path in required_items if not path.exists()]

            # Step 1: Check files and recover from GitHub if needed.
            self.after(0, lambda: self.splash_label.config(text='Checking Files\nPreparing system...'))
            self.after(0, lambda: self.splash_status.config(text='Step 1 of 4: File Check'))
            if missing_items:
                self.append_output('Missing setup items: ' + ', '.join(missing_items))
                self.append_output('Attempting GitHub repo download to repair setup...')
                if not self.download_and_extract():
                    self.append_output('GitHub download failed; continuing to main page anyway')
            else:
                self.append_output('Required setup items already present')
            
            # Step 2: Check required folders
            self.after(0, lambda: self.splash_label.config(text='Checking Folders\nValidating setup...'))
            self.after(0, lambda: self.splash_status.config(text='Step 2 of 4: Folder Check'))
            self.append_output('Step 2: Checking for required folders...')
            still_missing = self.check_folders()
            if still_missing:
                self.append_output('Missing items will not block startup: ' + ', '.join(still_missing))
            
            # Step 3: Install requirements
            self.after(0, lambda: self.splash_label.config(text='Installing Requirements\nSetting up packages...'))
            self.after(0, lambda: self.splash_status.config(text='Step 3 of 4: Installation'))
            self.append_output('Step 3: Installing Python requirements...')
            self.install_requirements()
            
            # Step 4: Re-import qrcode if available
            self.after(0, lambda: self.splash_label.config(text='Finalizing System\nAlmost ready...'))
            self.after(0, lambda: self.splash_status.config(text='Step 4 of 4: Finalizing'))
            self.append_output('Step 4: Checking for qrcode package...')
            try:
                import qrcode as _q
                globals()['qrcode'] = _q
                self.append_output('qrcode package available')
            except Exception:
                self.append_output('qrcode not yet installed, will install on first QR generation')
            
            self.append_output('=== STARTUP CHECKS COMPLETED ===')
            self.append_output('System ready. You can now start the server.')
            
            # Reset progress and show main window
            self.after(0, lambda: self.splash_progress.config(value=100))
            self.after(0, lambda: self.splash_status.config(text='100%'))
            self.after(0, self.reset_progress)
            self.after(500, lambda: (self.splash.destroy(), self.deiconify()))
        except Exception as e:
            self.append_output('Startup error: ' + str(e))
            # Still show main window on error
            self.after(0, lambda: self.splash_status.config(text='Error detected'))
            self.after(0, self.reset_progress)
            self.after(1000, lambda: (self.splash.destroy(), self.deiconify()))

    def ensure_runtime_directories(self):
        paths = [WORKSPACE, DATA_DIR]
        if not is_frozen_build():
            paths.append(get_runtime_static_dir())

        for path in paths:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

    def get_required_setup_items(self):
        items = [WORKSPACE / '3.11.9', WORKSPACE / 'data', WORKSPACE / 'requirements.txt']
        if not is_frozen_build():
            items.append(WORKSPACE / 'clinic')
        return items

    def download_and_extract(self):
        """Download and extract repo from GitHub if not already present."""
        # Check if required source folders already exist.
        if all(path.exists() for path in self.get_required_setup_items()):
            self.append_output('Required setup items already present, skipping download')
            return True
        
        self.append_output('Clinic folder not found, attempting download...')
        
        # First ensure requests is available
        if requests is None:
            self.append_output('Installing requests package first...')
            self.install_python_packages(['requests'])
            try:
                import requests as _req
                globals()['requests'] = _req
            except Exception as e:
                self.append_output('Failed to import requests: ' + str(e))
                return False
        
        url = 'https://github.com/venkatesh01-t/getdownload/archive/refs/heads/main.zip'
        dest_zip = WORKSPACE / 'repo.zip'
        self.append_output('Downloading repo from GitHub...')
        try:
            # Download with progress tracking
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()
            last_update_time = start_time
            last_downloaded = 0
            
            self.append_output(f'Total file size: {total_size / 1024 / 1024:.2f} MB')
            self.append_output('Starting download...')
            
            with open(dest_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress every 0.5 seconds
                        current_time = time.time()
                        if current_time - last_update_time >= 0.5 and total_size > 0:
                            # Calculate metrics
                            elapsed = current_time - start_time
                            downloaded_since_last = downloaded - last_downloaded
                            time_since_last = current_time - last_update_time
                            
                            # Speed in MBPS
                            speed_mbps = (downloaded_since_last / time_since_last) / (1024 * 1024)
                            
                            # Percentage
                            percentage = (downloaded / total_size) * 100
                            
                            # Time remaining
                            if speed_mbps > 0:
                                remaining_bytes = total_size - downloaded
                                remaining_seconds = remaining_bytes / (speed_mbps * 1024 * 1024)
                                remaining_time = timedelta(seconds=int(remaining_seconds))
                            else:
                                remaining_time = timedelta(seconds=0)
                            
                            # Format output
                            progress_msg = f'Download: {percentage:.1f}% | {downloaded / 1024 / 1024:.2f}/{total_size / 1024 / 1024:.2f} MB | Speed: {speed_mbps:.2f} MBPS | Time remaining: {remaining_time}'
                            self.append_output(progress_msg)
                            
                            # Update splash screen and UI with proper value capture
                            splash_text = f'Downloading...\n{percentage:.1f}% Complete'
                            self.after(0, lambda txt=splash_text: self.splash_label.config(text=txt))
                            self.after(0, lambda p=percentage: self.splash_progress.config(value=p))
                            self.after(0, lambda s=speed_mbps, t=remaining_time: (
                                self.splash_status.config(text=f'{s:.2f} MBPS | {t} remaining')
                            ))
                            
                            # Update progress bar with proper value capture
                            self.after(0, lambda p=percentage: self.update_progress(p))
                            
                            last_update_time = current_time
                            last_downloaded = downloaded
            
            self.append_output(f'Download complete: {downloaded / 1024 / 1024:.2f} MB downloaded')
            
            # Extract with progress tracking and error handling
            self.append_output('Extracting repository...')
            extraction_success = self.extract_zip_with_progress(dest_zip, WORKSPACE)
            
            if not extraction_success:
                self.append_output('ERROR: ZIP extraction failed, attempting recovery...')
                # Try alternative extraction method
                try:
                    self.append_output('Attempting alternative extraction method...')
                    extraction_success = self.extract_zip_alternative(dest_zip, WORKSPACE)
                except Exception as e:
                    self.append_output(f'Alternative extraction also failed: {str(e)}')
                    # Clean up and return on failure
                    if dest_zip.exists():
                        dest_zip.unlink()
                    return False
            
            # Find and move extracted content
            extracted_root = None
            for item in WORKSPACE.iterdir():
                if item.is_dir() and item.name.startswith('getdownload-'):
                    extracted_root = item
                    break
            
            if extracted_root:
                self.append_output(f'Merging extracted folder: {extracted_root.name}')
                try:
                    # Merge contents into workspace with error handling
                    for child in extracted_root.iterdir():
                        target = WORKSPACE / child.name
                        try:
                            if target.exists():
                                if target.is_dir():
                                    shutil.rmtree(target)
                                else:
                                    target.unlink()
                            if child.is_dir():
                                self.append_output(f'  Moving folder: {child.name}')
                                shutil.copytree(child, target)
                            else:
                                self.append_output(f'  Moving file: {child.name}')
                                shutil.copy2(child, target)
                        except Exception as e:
                            self.append_output(f'  WARNING: Failed to move {child.name}: {str(e)}')
                    
                    shutil.rmtree(extracted_root)
                except Exception as e:
                    self.append_output(f'ERROR during merge: {str(e)}')
            else:
                self.append_output('WARNING: Could not find extracted folder, checking for direct extraction...')
            
            # Clean up zip
            if dest_zip.exists():
                try:
                    dest_zip.unlink()
                    self.append_output('Cleaned up temporary ZIP file')
                except Exception as e:
                    self.append_output(f'WARNING: Could not delete ZIP file: {str(e)}')
            
            self.append_output('Repository extraction and merge complete')
            return True
        except Exception as e:
            self.append_output('Download/extract failed: ' + str(e))
            # Cleanup on error
            if dest_zip.exists():
                try:
                    dest_zip.unlink()
                except:
                    pass
            return False

    def extract_zip_with_progress(self, zip_path, extract_path):
        """Extract ZIP with comprehensive error handling, validation, and recovery."""
        try:
            # Validate inputs
            zip_path = Path(zip_path)
            extract_path = Path(extract_path)
            
            # Step 1: Pre-extraction validation
            self.append_output('Validating ZIP file...')
            
            # Check if ZIP file exists
            if not zip_path.exists():
                self.append_output(f'ERROR: ZIP file not found: {zip_path}')
                return False
            
            # Check if ZIP file is readable
            if not os.access(zip_path, os.R_OK):
                self.append_output(f'ERROR: ZIP file is not readable: {zip_path}')
                return False
            
            # Check if target directory exists, create if needed
            try:
                extract_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.append_output(f'ERROR: Cannot create extraction directory: {str(e)}')
                return False
            
            # Check if target directory is writable
            if not os.access(extract_path, os.W_OK):
                self.append_output(f'ERROR: Extraction directory is not writable: {extract_path}')
                return False
            
            # Check if ZIP file is valid
            try:
                if not zipfile.is_zipfile(zip_path):
                    self.append_output('ERROR: Invalid ZIP file format')
                    return False
            except Exception as e:
                self.append_output(f'ERROR: Cannot validate ZIP file: {str(e)}')
                return False
            
            # Step 2: Check disk space
            try:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    total_uncompressed = sum(info.file_size for info in z.infolist())
                
                stat = os.statvfs(extract_path) if hasattr(os, 'statvfs') else None
                if stat:
                    available_space = stat.f_bavail * stat.f_frsize
                    if available_space < total_uncompressed:
                        self.append_output(f'WARNING: Low disk space. Available: {available_space / 1024 / 1024:.1f} MB, Need: {total_uncompressed / 1024 / 1024:.1f} MB')
            except Exception as e:
                self.append_output(f'WARNING: Could not check disk space: {str(e)}')
            
            # Step 3: Extract with error handling
            self.append_output('Opening ZIP file for extraction...')
            
            extracted_files = []
            skipped_files = []
            failed_files = []
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    # Test ZIP integrity
                    test_result = z.testzip()
                    if test_result is not None:
                        self.append_output(f'WARNING: ZIP file may be corrupted. First bad file: {test_result}')
                    
                    file_list = z.namelist()
                    total_files = len(file_list)
                    
                    if total_files == 0:
                        self.append_output('WARNING: ZIP file is empty')
                        return True
                    
                    self.append_output(f'Starting extraction of {total_files} files...')
                    
                    start_time = time.time()
                    last_update_time = start_time
                    
                    for idx, file in enumerate(file_list, 1):
                        try:
                            # Skip directories
                            if file.endswith('/'):
                                extracted_files.append(file)
                                continue
                            
                            # Check for path issues (Windows max path length)
                            target_path = extract_path / file
                            full_path = str(target_path.resolve())
                            
                            if sys.platform == 'win32' and len(full_path) > 260:
                                self.append_output(f'WARNING: Path too long (Windows limit 260), skipping: {file}')
                                skipped_files.append(file)
                                continue
                            
                            # Create parent directory if needed
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Extract file with retry logic
                            max_retries = 2
                            for attempt in range(max_retries):
                                try:
                                    z.extract(file, extract_path)
                                    extracted_files.append(file)
                                    break
                                except PermissionError as pe:
                                    if attempt < max_retries - 1:
                                        self.append_output(f'RETRY {attempt + 1}: Permission issue with {file}, retrying...')
                                        time.sleep(0.5)
                                    else:
                                        raise
                                except Exception as fe:
                                    if attempt < max_retries - 1:
                                        self.append_output(f'RETRY {attempt + 1}: Extract issue with {file}, retrying...')
                                        time.sleep(0.5)
                                    else:
                                        raise
                        
                        except PermissionError as pe:
                            self.append_output(f'WARNING: Permission denied extracting {file}')
                            failed_files.append((file, str(pe)))
                        except UnicodeDecodeError as ue:
                            self.append_output(f'WARNING: Filename encoding issue with {file}')
                            skipped_files.append(file)
                        except Exception as fe:
                            self.append_output(f'WARNING: Failed to extract {file}: {str(fe)}')
                            failed_files.append((file, str(fe)))
                        
                        # Update progress every 0.5 seconds
                        current_time = time.time()
                        if current_time - last_update_time >= 0.5:
                            elapsed = current_time - start_time
                            percentage = (idx / total_files) * 100
                            
                            # Speed in files per second
                            speed_fps = idx / elapsed if elapsed > 0 else 0
                            
                            # Time remaining
                            if speed_fps > 0:
                                remaining_files = total_files - idx
                                remaining_seconds = remaining_files / speed_fps
                                remaining_time = timedelta(seconds=int(remaining_seconds))
                            else:
                                remaining_time = timedelta(seconds=0)
                            
                            progress_msg = f'Extract: {percentage:.1f}% | {idx}/{total_files} files | Speed: {speed_fps:.1f} files/sec | Time remaining: {remaining_time}'
                            self.append_output(progress_msg)
                            
                            # Update splash screen and UI with proper value capture
                            splash_text = f'Extracting...\n{percentage:.1f}% Complete'
                            self.after(0, lambda txt=splash_text: self.splash_label.config(text=txt))
                            self.after(0, lambda p=percentage: self.splash_progress.config(value=p))
                            self.after(0, lambda s=speed_fps, t=remaining_time: (
                                self.splash_status.config(text=f'{s:.1f} files/sec | {t} remaining')
                            ))
                            
                            # Update progress bar with proper value capture
                            self.after(0, lambda p=percentage: self.update_progress(p))
                            last_update_time = current_time
            
            except zipfile.BadZipFile as bz:
                self.append_output(f'ERROR: ZIP file is corrupted or invalid: {str(bz)}')
                return False
            except Exception as e:
                self.append_output(f'ERROR: Unexpected extraction error: {str(e)}')
                return False
            
            # Step 4: Report results
            self.append_output(f'Extraction complete:')
            self.append_output(f'  ✓ Successfully extracted: {len(extracted_files)} items')
            if skipped_files:
                self.append_output(f'  ⊘ Skipped: {len(skipped_files)} items')
            if failed_files:
                self.append_output(f'  ✗ Failed: {len(failed_files)} items')
                for file, reason in failed_files[:5]:  # Show first 5 failures
                    self.append_output(f'    - {file}: {reason}')
                if len(failed_files) > 5:
                    self.append_output(f'    ... and {len(failed_files) - 5} more failures')
            
            # Consider success if at least 90% of files extracted
            success_rate = len(extracted_files) / total_files if total_files > 0 else 0
            if success_rate >= 0.9:
                self.append_output(f'SUCCESS: Extraction successful with {success_rate*100:.1f}% success rate')
                return True
            elif success_rate >= 0.5:
                self.append_output(f'PARTIAL: Extraction partially successful with {success_rate*100:.1f}% success rate')
                return True
            else:
                self.append_output(f'FAILED: Extraction success rate too low ({success_rate*100:.1f}%)')
                return False
                
        except Exception as e:
            self.append_output(f'FATAL: Extraction error: {str(e)}')
            return False

    def extract_zip_alternative(self, zip_path, extract_path):
        """Alternative extraction method using Python's zipfile with different strategy."""
        try:
            zip_path = Path(zip_path)
            extract_path = Path(extract_path)
            
            self.append_output('Using alternative extraction method...')
            
            extract_path.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as z:
                file_list = z.namelist()
                total_files = len(file_list)
                
                extracted = 0
                failed = []
                
                for idx, file in enumerate(file_list, 1):
                    try:
                        # Read and write manually instead of using extract
                        if file.endswith('/'):
                            target = extract_path / file
                            target.mkdir(parents=True, exist_ok=True)
                            extracted += 1
                        else:
                            target = extract_path / file
                            target.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Write file content
                            with z.open(file) as source:
                                with open(target, 'wb') as dest:
                                    content = source.read()
                                    dest.write(content)
                            extracted += 1
                    except Exception as e:
                        failed.append((file, str(e)))
                
                self.append_output(f'Alternative extraction: {extracted}/{total_files} files extracted')
                if failed:
                    self.append_output(f'Alternative extraction: {len(failed)} files failed')
                return extracted / total_files >= 0.9
        except Exception as e:
            self.append_output(f'Alternative extraction failed: {str(e)}')
            return False

    def verify_extracted_files(self, extract_path):
        """Verify that critical files were extracted successfully."""
        try:
            extract_path = Path(extract_path)
            critical_files = ['clinic/manage.py', 'clinic/settings.py']
            
            self.append_output('Verifying extracted files...')
            
            found = 0
            for file_pattern in critical_files:
                target = extract_path / file_pattern
                if target.exists():
                    self.append_output(f'  ✓ Found: {file_pattern}')
                    found += 1
                else:
                    self.append_output(f'  ✗ Missing: {file_pattern}')
            
            return found >= len(critical_files) // 2  # At least 50% of critical files
        except Exception as e:
            self.append_output(f'File verification error: {str(e)}')
            return False

    def check_folders(self):
        expected = self.get_required_setup_items()
        missing = [str(path) for path in expected if not path.exists()]
        if missing:
            self.append_output('Missing folders: ' + ', '.join(missing))
        else:
            self.append_output('All expected folders present')
        return missing

    def install_requirements(self):
        """Install all packages from requirement.txt."""
        if is_frozen_build():
            self.append_output('Frozen build detected, skipping runtime requirements installation')
            return True

        req = WORKSPACE / 'requirements.txt'
        if not PYTHON_EXE.exists():
            self.append_output(f'Python not found at {PYTHON_EXE}')
            return False
        if not req.exists():
            self.append_output('requirement.txt not found, skipping')
            return False
        
        self.append_output('Installing requirements from requirement.txt...')
        cmd = [str(PYTHON_EXE), '-m', 'pip', 'install', '-r', str(req)]
        try:
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=CREATE_NO_WINDOW)
            if proc.stdout:
                self.append_output(proc.stdout)
            if proc.stderr and proc.returncode != 0:
                self.append_output('Errors: ' + proc.stderr)
            if proc.returncode == 0:
                self.append_output('Requirements installed successfully')
                return True
            else:
                self.append_output('Some requirements may have failed to install')
                return False
        except Exception as e:
            self.append_output('Requirements install failed: ' + str(e))
            return False

    def install_python_packages(self, packages):
        """Install pip packages using bundled Python."""
        if is_frozen_build():
            self.append_output('Frozen build detected, skipping package install')
            return False

        if not PYTHON_EXE.exists():
            self.append_output(f'Python not found at {PYTHON_EXE}')
            return False
        cmd = [str(PYTHON_EXE), '-m', 'pip', 'install'] + packages
        self.append_output('Installing packages: ' + ' '.join(packages))
        try:
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, creationflags=CREATE_NO_WINDOW)
            if proc.stdout:
                self.append_output(proc.stdout)
            if proc.stderr:
                self.append_output(proc.stderr)
            return proc.returncode == 0
        except Exception as e:
            self.append_output('Package install failed: ' + str(e))
            return False

    def ensure_qrcode(self):
        """Ensure qrcode package is installed (Pillow not needed for fallback QR rendering)."""
        global qrcode
        if qrcode is not None:
            self.append_output('qrcode already available')
            return True

        if is_frozen_build():
            self.append_output('Frozen build detected, qrcode must be bundled at build time')
            try:
                import qrcode as _q
                qrcode = _q
                self.append_output('qrcode imported successfully')
                return True
            except Exception as e:
                self.append_output('qrcode import failed in frozen build: ' + str(e))
                return False
        
        self.append_output('Installing qrcode package...')
        ok = self.install_python_packages(['qrcode[pil]'])
        if not ok:
            self.append_output('Failed to install qrcode; will attempt fallback rendering')
            return False
        
        try:
            import qrcode as _q
            qrcode = _q
            self.append_output('qrcode imported successfully')
            return True
        except Exception as e:
            self.append_output('qrcode import failed: ' + str(e))
            return False

    def find_local_ip(self):
        """Find local IP address with multiple fallback methods."""
        # Method 1: Try connecting to external DNS (Google)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and ip != '127.0.0.1':
                return ip
        except Exception as e:
            self.append_output(f'Method 1 (Google DNS) failed: {str(e)}')
        
        # Method 2: Try connecting to Cloudflare DNS
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(('1.1.1.1', 53))
            ip = s.getsockname()[0]
            s.close()
            if ip and ip != '127.0.0.1':
                return ip
        except Exception as e:
            self.append_output(f'Method 2 (Cloudflare DNS) failed: {str(e)}')
        
        # Method 3: Try localhost (fallback)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(('localhost', 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and ip != '127.0.0.1':
                return ip
        except Exception:
            pass
        
        # Method 4: Use hostname resolution
        try:
            import socket as sock
            hostname = sock.gethostname()
            ip = sock.gethostbyname(hostname)
            if ip and ip != '127.0.0.1':
                self.append_output(f'Using hostname resolution: {ip}')
                return ip
        except Exception:
            pass
        
        # Final fallback
        self.append_output('WARNING: Could not detect local IP, using localhost')
        return '127.0.0.1'

    def network_monitor(self):
        """Monitor for network/IP address changes and update server URL automatically."""
        self.network_monitor_running = True
        consecutive_errors = 0
        
        while self.network_monitor_running and self.server_running:
            try:
                # Check for IP change every 5 seconds (rate limiting)
                current_time = time.time()
                if current_time - self.last_ip_check_time < 5:
                    time.sleep(0.5)
                    continue
                
                self.last_ip_check_time = current_time
                
                # Get current IP
                new_ip = self.find_local_ip()
                
                # Check if IP has changed
                if self.current_ip is not None and new_ip != self.current_ip:
                    self.append_output(f'⚠️ NETWORK CHANGE DETECTED: IP changed from {self.current_ip} to {new_ip}')
                    self.update_server_url_for_network_change(new_ip)
                    consecutive_errors = 0
                
                self.current_ip = new_ip
                consecutive_errors = 0
                
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors <= 3:  # Log first 3 errors only
                    self.append_output(f'Network monitor error: {str(e)}')
                
                if consecutive_errors > 10:
                    self.append_output('Network monitor: Too many errors, stopping monitoring')
                    self.network_monitor_running = False
                
                time.sleep(1)

    def update_server_url_for_network_change(self, new_ip):
        """Update server URL and QR code when network/IP changes."""
        try:
            old_url = self.url_var.get()
            new_url = f'http://{new_ip}:{self.server_port}'
            
            # Only update if URL actually changed
            if old_url != new_url:
                self.append_output(f'⚠️ NETWORK CHANGE - Updating server URL')
                self.append_output(f'   Old: {old_url}')
                self.append_output(f'   New: {new_url}')
                
                # Update in main thread
                self.after(0, lambda: self.url_var.set(new_url))
                
                # Regenerate QR code
                self.after(0, lambda: self.generate_qr(new_url))
                
                # Update access methods display
                self.after(0, self.update_access_methods_display)
                
                # Log the change
                self.append_output(f'✓ Server URL updated successfully')
                self.append_output(f'✓ QR code regenerated for new network')
                self.append_output(f'✓ Access methods panel updated')
            
        except Exception as e:
            self.append_output(f'ERROR updating server URL: {str(e)}')

    def show_network_access_methods(self):
        """Display all methods to access the server."""
        try:
            ip = self.current_ip
            port = self.server_port
            
            self.append_output('=' * 60)
            self.append_output('📱 NETWORK ACCESS METHODS (No Internet Required):')
            self.append_output('=' * 60)
            self.append_output(f'  🖥️  Same Computer:')
            self.append_output(f'     • http://localhost:{port}')
            self.append_output(f'     • http://127.0.0.1:{port}')
            self.append_output(f'  � Other Devices (Same WiFi):')
            self.append_output(f'     • http://{ip}:{port}')
            try:
                hostname = socket.gethostname()
                self.append_output(f'     • http://{hostname}:{port}')
            except:
                pass
            self.append_output('=' * 60)
        except Exception as e:
            self.append_output(f'Error showing access methods: {str(e)}')

    def is_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return False
            except OSError:
                return True

    def update_access_methods_display(self):
        """Update the UI panel with current access methods."""
        try:
            port = self.server_port
            ip = self.current_ip if self.current_ip else '192.168.x.x'
            
            # Update labels with current values
            self.localhost_label.config(text=f'🔗 http://localhost:{port}')
            self.loopback_label.config(text=f'🔗 http://127.0.0.1:{port}')
            self.ip_label.config(text=f'🔗 http://{ip}:{port}')
            
            try:
                hostname = socket.gethostname()
                self.hostname_label.config(text=f'🔗 http://{hostname}:{port}')
            except:
                self.hostname_label.config(text='🔗 http://[hostname]:[port]')
        except Exception as e:
            self.append_output(f'Error updating access methods display: {str(e)}')

    def start_server(self):
        if not is_frozen_build() and not PYTHON_EXE.exists():
            self.append_output(f'Python executable not found at {PYTHON_EXE}')
            return
        port = int(self.port_var.get())
        start_port = port
        while self.is_port_in_use(port):
            self.append_output(f'Port {port} is in use, trying next')
            port += 1
            if port > start_port + 20:
                self.append_output('No free port found in range')
                return
        self.port_var.set(port)
        self.server_port = port  # Save the actual port being used
        self.append_output('Starting server on port ' + str(port))
        
        # Start server with HIDDEN console - fully in background
        try:
            cmd = get_server_command(port)

            if sys.platform == 'win32':
                # Windows: Hide the console window completely
                CREATE_NO_WINDOW = 0x08000000
                self.server_process = subprocess.Popen(
                    cmd,
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=self.get_server_environment(),
                )
                self.append_output('✓ Server started in background (hidden)...')
            else:
                # On Linux/Mac, run in background
                self.server_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
                    env=self.get_server_environment(),
                )
                self.append_output('✓ Server started in background (hidden)...')
        except Exception as e:
            self.append_output(f'ERROR: Failed to start server: {str(e)}')
            return
        
        self.server_running = True
        
        # Disable Start Server button and enable Stop/Browser buttons
        if not ctk:
            try:
                self.start_btn.config(state='disabled')
                self.stop_btn.config(state='normal')
                self.browser_btn.config(state='normal')
            except Exception:
                pass

        # update URL and QR
        ip = self.find_local_ip()
        self.current_ip = ip  # Track the initial IP
        url = f'http://{ip}:{port}'
        self.url_var.set(url)
        self.generate_qr(url)
        
        # Update the access methods display panel
        self.update_access_methods_display()
        self.append_output(f'✓ Server started on port {port}')
        self.append_output(f'✓ Server accessible at: {url}')
        self.append_output('✓ Check the Network Access Methods panel above for all connection options')
        self.after(500, self.open_browser)

        # Start network monitor to detect IP/network changes
        self.append_output('✓ Starting network monitor for automatic URL updates')
        monitor_thread = threading.Thread(target=self.network_monitor, daemon=True, name='NetworkMonitor')
        monitor_thread.start()

        # Monitor server process in background
        def monitor_server():
            try:
                if self.server_process:
                    self.server_process.wait()  # Wait for server process to end
                    self.server_running = False
                    self.network_monitor_running = False
                    self.after(0, self.on_server_stopped)
            except Exception as e:
                pass
        
        threading.Thread(target=monitor_server, daemon=True).start()

    def get_server_environment(self):
        env = os.environ.copy()
        env['CLINIC_DATA_DIR'] = str(DATA_DIR)
        env['CLINIC_STATIC_ROOT'] = str(get_runtime_static_dir())
        return env

    def open_browser(self):
        """Open the server URL in default web browser."""
        if not self.server_running:
            messagebox.showwarning('Server Not Running', 'Please start the server first')
            return
        
        try:
            import webbrowser
            port = self.server_port or int(self.port_var.get() or 8000)
            url = f'http://localhost:{port}'
            self.append_output(f'Opening browser: {url}')
            webbrowser.open(url)
        except Exception as e:
            self.append_output(f'Failed to open browser: {str(e)}')
            messagebox.showerror('Error', f'Could not open browser: {str(e)}')

    def kill_process_on_port(self, port: int):
        """Kill any process using the specified port (fallback method)."""
        try:
            if sys.platform == 'win32':
                # Windows: use netstat and taskkill
                CREATE_NO_WINDOW = 0x08000000
                result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
                for line in result.stdout.split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if parts:
                            pid = parts[-1]
                            try:
                                subprocess.run(['taskkill', '/F', '/PID', pid], 
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, creationflags=CREATE_NO_WINDOW)
                                self.append_output(f'Killed process {pid} on port {port}')
                            except Exception:
                                pass
            else:
                # Linux/Mac: use lsof and kill
                result = subprocess.run(['lsof', '-i', f':{port}'], capture_output=True, text=True, timeout=5, preexec_fn=os.setsid if hasattr(os, 'setsid') else None)
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        try:
                            subprocess.run(['kill', '-9', pid], timeout=3, preexec_fn=os.setsid if hasattr(os, 'setsid') else None)
                            self.append_output(f'Killed process {pid} on port {port}')
                        except Exception:
                            pass
        except Exception as e:
            self.append_output(f'Error killing process on port {port}: {str(e)}')

    def on_server_stopped(self):
        """Handle server process stopping (called when server exits on its own)."""
        try:
            self.append_output('Server process stopped')
            self.server_running = False
            self.network_monitor_running = False
            self.url_var.set('')
            try:
                self.qr_canvas.delete('all')
            except Exception:
                pass
            
            # Re-enable Start Server button and disable Stop/Browser buttons
            if not ctk:
                try:
                    self.start_btn.config(state='normal')
                    self.stop_btn.config(state='disabled')
                    self.browser_btn.config(state='disabled')
                except Exception:
                    pass
        except Exception as e:
            self.append_output(f'Error in on_server_stopped: {str(e)}')

    def stop_server(self):
        if self.server_running:
            self.append_output('Stopping server...')
            self.network_monitor_running = False
            
            # Try to terminate the process
            if self.server_process:
                try:
                    if sys.platform == 'win32':
                        # On Windows, use terminate then kill if needed
                        try:
                            self.server_process.terminate()
                            self.server_process.wait(timeout=2)
                            self.append_output('Server process terminated gracefully')
                        except subprocess.TimeoutExpired:
                            self.server_process.kill()
                            self.append_output('Server process killed')
                    else:
                        # On Unix/Linux, use terminate then kill
                        try:
                            self.server_process.terminate()
                            self.server_process.wait(timeout=3)
                            self.append_output('Server process terminated gracefully')
                        except subprocess.TimeoutExpired:
                            self.server_process.kill()
                            self.append_output('Server process killed')
                except Exception as e:
                    self.append_output(f'Error stopping process: {str(e)}')
            
            # Fallback: kill any remaining process on the port
            self.kill_process_on_port(self.server_port)
            
            # Clean up UI
            self.server_process = None
            self.server_running = False
            self.url_var.set('')
            try:
                self.qr_canvas.delete('all')
            except Exception:
                pass
            
            # Re-enable Start Server button and disable Stop/Browser buttons
            if not ctk:
                try:
                    self.start_btn.config(state='normal')
                    self.stop_btn.config(state='disabled')
                    self.browser_btn.config(state='disabled')
                except Exception:
                    pass
            
            self.append_output('✓ Server stopped')
        else:
            self.append_output('Server is not running')

    def on_closing(self):
        """Handle window close event - cleanup server properly."""
        self.append_output('Closing application...')
        # Stop the server if it's running
        if self.server_running:
            self.append_output('Server still running, stopping before close...')
            self.stop_server()
        # Destroy the window
        self.destroy()
        # Force exit to ensure all processes are terminated
        import sys
        sys.exit(0)

    def generate_qr(self, text: str):
        """Generate and draw QR code on canvas using fallback matrix drawing (no Pillow needed)."""
        if qrcode is None:
            self.append_output('qrcode not available; installing...')
            self.ensure_qrcode()
            if qrcode is None:
                self.append_output('Could not install qrcode; QR display unavailable')
                return

        try:
            # Clear canvas
            self.qr_canvas.delete('all')
            
            # Generate QR matrix
            qr_obj = qrcode.QRCode(border=2)
            qr_obj.add_data(text)
            qr_obj.make(fit=True)
            matrix = qr_obj.get_matrix()
            
            rows = len(matrix)
            cols = len(matrix[0]) if rows else 0
            if rows == 0 or cols == 0:
                return
            
            # Draw QR on canvas (200x200 pixels with padding)
            canvas_size = 200
            padding = 5
            usable_size = canvas_size - 2 * padding
            px = usable_size / max(rows, cols)
            
            for r in range(rows):
                for c in range(cols):
                    if matrix[r][c]:
                        x0 = padding + c * px
                        y0 = padding + r * px
                        x1 = x0 + px
                        y1 = y0 + px
                        self.qr_canvas.create_rectangle(x0, y0, x1, y1, fill='black', outline='')
            
            self.append_output('QR code generated successfully')
        except Exception as e:
            self.append_output('QR generation failed: ' + str(e))

    def backup_data(self):
        if not DATA_DIR.exists():
            self.append_output('No data folder to backup')
            return
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        target = WORKSPACE / f'data-backup-{timestamp}.zip'
        self.append_output(f'Creating backup {target}...')
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(DATA_DIR):
                for f in files:
                    full = Path(root) / f
                    arc = full.relative_to(WORKSPACE)
                    z.write(full, arc)
        self.append_output('Backup complete: ' + str(target))

    def restore_data(self):
        path = filedialog.askopenfilename(title='Select backup zip', filetypes=[('Zip files', '*.zip')])
        if not path:
            return
        self.append_output('Restoring from ' + path)
        try:
            # remove existing data (keep safe: move to .old)
            if DATA_DIR.exists():
                old = WORKSPACE / f'data.old.{int(time.time())}'
                shutil.move(str(DATA_DIR), str(old))
                self.append_output('Moved existing data to ' + str(old))
            with zipfile.ZipFile(path, 'r') as z:
                z.extractall(WORKSPACE)
            self.append_output('Restore complete')
        except Exception as e:
            self.append_output('Restore failed: ' + str(e))


def main():
    app = ClinicManager()
    app.mainloop()


if maybe_run_server_mode():
    raise SystemExit(0)

if __name__ == '__main__':
    main()


# ============================================================================
# PYINSTALLER COMPILATION INSTRUCTIONS
# ============================================================================
"""
COMPILE TO EXE WITH PYINSTALLER:

1. Install PyInstaller:
   pip install pyinstaller

2. Compile with GUI only (no main console):
   pyinstaller --onefile --noconsole ^
         --add-data "clinic_manager_data\\clinic;clinic" ^
       --hidden-import=customtkinter ^
       --hidden-import=qrcode ^
       --hidden-import=requests ^
       --hidden-import=waitress ^
       clinic_manager.py
   
   This creates:
   - clinic_manager.dist/ folder with exe
   - clinic_manager.exe ready to use
   
3. Run the exe:
   - Double-click clinic_manager.exe
   - Main GUI window appears (no console)
   - Data folder created: clinic_manager_data\
   
4. When you click "Start Server":
   - New console window opens automatically
   - Server output shows in the new console
   - Server runs in background on the new console
   
5. First run setup:
    - Uses the clinic project bundled inside the exe
    - Creates the external clinic_manager_data folder next to the exe
    - Stores database and uploads outside the temp bundle so they persist
    - Bundled server mode starts automatically from the same exe

EXECUTION FLOW:
   EXE Start → Splash Screen → File Download (Background) → 
   Extract Repo (Background) → Install Packages (Background) → 
   Main GUI (No Console) → Click "Start Server" → 
   New Console Window Opens → Server Runs Visible

NOTE: Server console is separate from main GUI, so you can:
   - See all server output in real-time
   - Keep main GUI running
   - Stop server from main GUI
   - Close server console independently

BUILD SCRIPT:
   Use BUILD_EXE.bat to compile automatically with all flags set correctly
"""
