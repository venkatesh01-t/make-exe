import os
import sys
import json
import hashlib
import shutil
import zipfile
import threading
import subprocess
import socket
import time
import queue
import ctypes
from pathlib import Path
from datetime import datetime, timedelta

# Try to import customtkinter for modern UI
try:
    import customtkinter as ctk
except ImportError:
    ctk = None

import tkinter as tk
from tkinter import messagebox, ttk

# Try to import requests (might be missing initially)
try:
    import requests
except ImportError:
    requests = None

# QR Code placeholder (will be imported later or use fallback)
qrcode = None

# ============================================================================
# ADMIN CHECK & ELEVATION
# ============================================================================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def relaunch_as_admin():
    if sys.platform == 'win32' and not is_admin():
        # Get the path to the current executable
        # If running as script, sys.executable is python.exe, sys.argv[0] is script
        # If running as Nuitka exe, sys.executable is the exe
        script = sys.argv[0]
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        
        # Determine if we are running as an EXE
        is_exe = getattr(sys, 'frozen', False) or sys.executable.lower().endswith('.exe')
        
        if is_exe:
            executable = sys.executable
            arguments = params
        else:
            executable = sys.executable
            arguments = f'"{script}" {params}'
            
        ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, arguments, None, 1)
        sys.exit()

# Perform admin check early
relaunch_as_admin()

# ============================================================================
# PATH CONFIGURATION
# ============================================================================
def get_app_root():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

APP_ROOT = get_app_root()
RUNTIME_DIR = APP_ROOT / "3.11.9"
PYTHON_EXE = RUNTIME_DIR / "python.exe"
DATA_DIR = APP_ROOT / "data"
REQUIREMENTS_FILE = APP_ROOT / "requirement.txt"
HASH_FILE = APP_ROOT / ".req_hash"
LOG_FILE = APP_ROOT / "clinic_manager.log"
GITHUB_REPO_ZIP = "https://github.com/venkatesh01-t/getdownload/archive/refs/heads/main.zip"

# ============================================================================
# CONSTANTS
# ============================================================================
VERSION = "1.0.0"
REPO_OWNER = "venkatesh01-t"
REPO_NAME = "getdownload"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except:
        pass

# ============================================================================
# UTILITIES
# ============================================================================
def get_file_hash(filepath):
    if not os.path.exists(filepath):
        return None
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# ============================================================================
# GUI & LOGIC
# ============================================================================
class ClinicManagerApp(ctk.CTk if ctk else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Clinic Manager Dashboard")
        self.geometry("800x600")
        if ctk:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
        
        self.server_process = None
        self.server_running = False
        self.log_queue = queue.Queue()
        
        # Setup UI
        self.setup_ui()
        
        # Withdraw main window and show splash
        self.withdraw()
        self.show_splash()
        
        # Start background initialization
        threading.Thread(target=self.initialize_system, daemon=True).start()

    def show_splash(self):
        self.splash = tk.Toplevel(self)
        self.splash.title("Loading...")
        self.splash.geometry("400x250")
        self.splash.overrideredirect(True)
        
        # Center splash
        screen_width = self.splash.winfo_screenwidth()
        screen_height = self.splash.winfo_screenheight()
        x = (screen_width // 2) - (400 // 2)
        y = (screen_height // 2) - (250 // 2)
        self.splash.geometry(f"+{x}+{y}")
        
        self.splash_frame = tk.Frame(self.splash, bg="#2c3e50", relief="raised", borderwidth=2)
        self.splash_frame.pack(fill="both", expand=True)
        
        tk.Label(self.splash_frame, text="CLINIC MANAGER", font=("Segoe UI", 20, "bold"), fg="white", bg="#2c3e50").pack(pady=(40, 10))
        self.splash_status = tk.Label(self.splash_frame, text="Initializing...", font=("Segoe UI", 10), fg="#bdc3c7", bg="#2c3e50")
        self.splash_status.pack(pady=10)
        
        self.splash_progress = ttk.Progressbar(self.splash_frame, length=300, mode="determinate")
        self.splash_progress.pack(pady=20)
        
        self.splash.update()

    def update_splash(self, text, progress):
        self.splash_status.config(text=text)
        self.splash_progress["value"] = progress
        self.splash.update()

    def setup_ui(self):
        # Control Panel
        self.control_frame = ctk.CTkFrame(self) if ctk else tk.Frame(self, bg="#34495e")
        self.control_frame.pack(side="top", fill="x", padx=10, pady=10)
        
        if ctk:
            self.start_btn = ctk.CTkButton(self.control_frame, text="Start Server", command=self.start_server_thread)
            self.start_btn.pack(side="left", padx=10, pady=10)
            
            self.stop_btn = ctk.CTkButton(self.control_frame, text="Stop Server", command=self.stop_server, state="disabled")
            self.stop_btn.pack(side="left", padx=10, pady=10)
            
            self.browser_btn = ctk.CTkButton(self.control_frame, text="Open Browser", command=self.open_browser, state="disabled")
            self.browser_btn.pack(side="left", padx=10, pady=10)

            self.update_btn = ctk.CTkButton(self.control_frame, text="Check Updates", command=self.check_for_updates)
            self.update_btn.pack(side="right", padx=10, pady=10)
        else:
            self.start_btn = tk.Button(self.control_frame, text="Start Server", command=self.start_server_thread)
            self.start_btn.pack(side="left", padx=10, pady=10)
            
            self.stop_btn = tk.Button(self.control_frame, text="Stop Server", command=self.stop_server, state="disabled")
            self.stop_btn.pack(side="left", padx=10, pady=10)
            
            self.browser_btn = tk.Button(self.control_frame, text="Open Browser", command=self.open_browser, state="disabled")
            self.browser_btn.pack(side="left", padx=10, pady=10)

            self.update_btn = tk.Button(self.control_frame, text="Check Updates", command=self.check_for_updates)
            self.update_btn.pack(side="right", padx=10, pady=10)

    def check_for_updates(self):
        threading.Thread(target=self._check_for_updates_bg, daemon=True).start()

    def _check_for_updates_bg(self):
        try:
            self.log("Checking for updates...")
            if requests is None:
                self.log("Update check skipped: 'requests' module not available.")
                return

            response = requests.get(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest", timeout=10)
            if response.status_code == 200:
                data = response.json()
                latest_tag = data.get("tag_name", "0.0.0").strip("v")
                if self.compare_versions(latest_tag, VERSION):
                    if messagebox.askyesno("Update Available", f"A new version v{latest_tag} is available. Download and update?"):
                        assets = data.get("assets", [])
                        exe_url = None
                        for asset in assets:
                            if asset["name"].endswith(".exe"):
                                exe_url = asset["browser_download_url"]
                                break
                        
                        if exe_url:
                            self.perform_update(exe_url)
                        else:
                            self.log("No executable asset found in the latest release.")
                else:
                    self.log(f"You are running the latest version (v{VERSION}).")
            else:
                self.log("No updates found on GitHub.")
        except Exception as e:
            self.log(f"Update Check Error: {e}")

    def compare_versions(self, v1, v2):
        try:
            return [int(x) for x in v1.split(".")] > [int(x) for x in v2.split(".")]
        except:
            return v1 > v2

    def perform_update(self, url):
        try:
            self.log("Downloading update...")
            response = requests.get(url, stream=True)
            new_exe = APP_ROOT / "main_new.exe"
            with open(new_exe, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.log("Update downloaded. Restarting to apply...")
            batch_path = APP_ROOT / "update.bat"
            current_exe = sys.executable
            
            with open(batch_path, "w") as f:
                f.write(f'@echo off\n')
                f.write(f'timeout /t 2 /nobreak > nul\n')
                f.write(f'del "{current_exe}"\n')
                f.write(f'rename "{new_exe}" "{Path(current_exe).name}"\n')
                f.write(f'start "" "{current_exe}"\n')
                f.write(f'del "%~f0"\n')
            
            os.startfile(batch_path)
            self.after(0, self.destroy)
            sys.exit()
        except Exception as e:
            self.log(f"Update failed: {e}")
            
        # Status/Info Area
        self.info_frame = ctk.CTkFrame(self) if ctk else tk.Frame(self)
        self.info_frame.pack(side="top", fill="x", padx=10, pady=5)
        
        self.url_label = ctk.CTkLabel(self.info_frame, text="Server URL: Not Running") if ctk else tk.Label(self.info_frame, text="Server URL: Not Running")
        self.url_label.pack(side="left", padx=10)
        
        # QR Code Canvas
        self.qr_canvas = tk.Canvas(self, width=200, height=200, bg="white")
        self.qr_canvas.pack(pady=10)
        
        # Log Area
        self.log_text = tk.Text(self, height=15, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.after(100, self.process_logs)

    def log(self, msg):
        self.log_queue.put(msg)
        log(msg)

    def process_logs(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_text.insert("end", f"{msg}\n")
            self.log_text.see("end")
        self.after(100, self.process_logs)

    # ========================================================================
    # INITIALIZATION LOGIC
    # ========================================================================
    def initialize_system(self):
        try:
            # 1. Check/Download Runtime
            if not PYTHON_EXE.exists():
                self.log("Embedded Python runtime missing. Downloading...")
                self.update_splash("Downloading Runtime...", 20)
                self.download_runtime()
            
            # 2. Check/Install Requirements
            self.update_splash("Checking Dependencies...", 60)
            self.check_dependencies()
            
            # 3. Finalize
            self.update_splash("Finalizing...", 90)
            time.sleep(0.5)
            
            self.log("System initialized successfully.")
            self.after(0, self.finish_init)
            
        except Exception as e:
            self.log(f"Initialization Error: {e}")
            messagebox.showerror("Init Error", f"Failed to initialize: {e}")
            self.after(0, self.destroy)

    def finish_init(self):
        self.splash.destroy()
        self.deiconify()

    def download_runtime(self):
        global requests
        # If requests is missing, we need to bootstrap it. But if we are in Nuitka, we should have it.
        if requests is None:
            self.log("Installing requests for bootstrapping...")
            # We don't have a python exe yet to run pip! 
            # This is why the manager should be compiled with requests included.
            raise Exception("Critical: 'requests' module missing in manager.")

        response = requests.get(GITHUB_REPO_ZIP, stream=True)
        response.raise_for_status()
        
        zip_path = APP_ROOT / "temp_repo.zip"
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        self.log("Extracting runtime and data...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(APP_ROOT / "temp_extract")
            
        # Move files from temp_extract/getdownload-main/* to APP_ROOT
        extract_root = APP_ROOT / "temp_extract" / "getdownload-main"
        for item in extract_root.iterdir():
            dest = APP_ROOT / item.name
            if dest.exists():
                if dest.is_dir(): shutil.rmtree(dest)
                else: dest.unlink()
            shutil.move(str(item), str(APP_ROOT))
            
        # Cleanup
        shutil.rmtree(APP_ROOT / "temp_extract")
        zip_path.unlink()
        self.log("Runtime and data setup complete.")

    def check_dependencies(self):
        if not REQUIREMENTS_FILE.exists():
            self.log("requirement.txt not found. Skipping dependency check.")
            return

        current_hash = get_file_hash(REQUIREMENTS_FILE)
        stored_hash = None
        if HASH_FILE.exists():
            stored_hash = HASH_FILE.read_text().strip()

        if current_hash != stored_hash:
            self.log("Changes detected in requirements or first run. Installing...")
            cmd = [str(PYTHON_EXE), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)]
            try:
                # On Windows, CREATE_NO_WINDOW = 0x08000000
                subprocess.run(cmd, check=True, creationflags=0x08000000)
                HASH_FILE.write_text(current_hash)
                self.log("Dependencies installed successfully.")
            except subprocess.CalledProcessError as e:
                self.log(f"Pip installation failed: {e}")
        else:
            self.log("Dependencies are up to date.")

    # ========================================================================
    # SERVER LOGIC
    # ========================================================================
    def start_server_thread(self):
        threading.Thread(target=self.start_server, daemon=True).start()

    def start_server(self):
        if self.server_running: return
        
        port = 8000
        # Check if port is free, find next if not
        while self.is_port_in_use(port):
            port += 1
            if port > 8100:
                self.log("Error: No free ports found.")
                return
        
        self.log(f"Starting server on port {port}...")
        
        # Determine local IP
        local_ip = self.get_local_ip()
        server_url = f"http://{local_ip}:{port}"
        
        # Launch Waitress via Django (assumed manage.py or a wsgi script is present)
        # For simplicity, we'll try to run manage.py runserver if waitress isn't configured in code
        # But for "hide and secure", it's better to use waitress-serve or a script
        
        cmd = [str(PYTHON_EXE), "-c", f"import os, sys; sys.path.append(os.getcwd()); from waitress import serve; from clinic.wsgi import application; print('Server starting...'); serve(application, host='0.0.0.0', port={port})"]
        
        try:
            self.server_process = subprocess.Popen(
                cmd,
                cwd=str(APP_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=0x08000000
            )
            self.server_running = True
            
            # Update UI
            self.after(0, lambda: self.on_server_start_ui(server_url))
            
            # Monitor output
            for line in iter(self.server_process.stdout.readline, ""):
                if line: self.log(f"[Server] {line.strip()}")
            
        except Exception as e:
            self.log(f"Server Error: {e}")
            self.server_running = False

    def on_server_start_ui(self, url):
        self.url_label.configure(text=f"Server URL: {url}")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.browser_btn.configure(state="normal")
        self.generate_qr(url)

    def stop_server(self):
        if self.server_process:
            self.log("Stopping server...")
            # On Windows, we might need taskkill to be sure
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.server_process.pid)], creationflags=0x08000000)
            self.server_process = None
            self.server_running = False
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.browser_btn.configure(state="disabled")
            self.url_label.configure(text="Server URL: Stopped")
            self.qr_canvas.delete("all")
            self.log("Server stopped.")

    def open_browser(self):
        import webbrowser
        url = self.url_label.cget("text").replace("Server URL: ", "")
        webbrowser.open(url)

    def is_port_in_use(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def generate_qr(self, url):
        global qrcode
        if qrcode is None:
            try:
                import qrcode as _q
                qrcode = _q
            except ImportError:
                self.log("qrcode library missing. Cannot show QR.")
                return

        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        
        self.qr_canvas.delete("all")
        size = len(matrix)
        px = 200 / size
        for r in range(size):
            for c in range(size):
                if matrix[r][c]:
                    self.qr_canvas.create_rectangle(c*px, r*px, (c+1)*px, (r+1)*px, fill="black", outline="")

if __name__ == "__main__":
    app = ClinicManagerApp()
    app.mainloop()
