import os
import sys
import threading
import queue
import subprocess
import socket
import time
from pathlib import Path
from PIL import Image

import customtkinter as ctk
from models.config.settings import WORKSPACE, DATA_DIR, APP_ROOT, PYTHON_EXE, get_runtime_static_dir
from models.utils.os_helpers import apply_window_icon, set_windows_taskbar_icon, log, is_frozen_build
from models.utils.network import find_local_ip, is_port_in_use, network_monitor
from models.core.server import get_server_command, kill_process_on_port
from models.core.installer import (
    ensure_runtime_directories, get_required_setup_items, check_folders,
    install_python_packages, install_requirements, ensure_qrcode
)
from models.core.downloader import download_and_extract
from models.core.backup import backup_data, restore_data
from models.ui.splash import SplashScreen
from models.ui.components import PrimaryButton, GhostButton, DangerButton
from models.ui.components import generate_qr
from models.design_system.tokens import Colors
from models.design_system.fonts import make_font, Fonts

class ClinicManager(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Clinic Manager")
        apply_window_icon(self, APP_ROOT)
        try:
            set_windows_taskbar_icon(self, APP_ROOT)
        except Exception:
            pass
        self.geometry("1100x750")
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=Colors.pair(Colors.BG, Colors.DARK_BG))
        
        # Variables
        self.url_var = ctk.StringVar(value="http://127.0.0.1:8000")
        self.port_var = ctk.IntVar(value=8000)
        self.server_process = None
        self.server_running = False
        self.output_queue = queue.Queue()
        self.server_port = 8000
        self.current_ip = None
        
        # Navigation state
        self.nav_buttons = {}
        self.pages = {}
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.withdraw()
        
        # Splash
        self.splash = SplashScreen(self)
        
        self._setup_ui()
        self.after(100, self.process_output_queue)
        
        # Start in Dashboard
        self.select_page("dashboard")
        
        threading.Thread(target=self.startup_checks, daemon=True).start()

    def _setup_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, 
                                    fg_color=Colors.pair(Colors.SURFACE, Colors.DARK_SURFACE))
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Logo in Sidebar
        self._load_sidebar_logo()
        
        # Navigation Items
        self._setup_navigation()
        
        # Main Content Area
        self.main_view = ctk.CTkFrame(self, fg_color="transparent")
        self.main_view.pack(side="right", fill="both", expand=True, padx=30, pady=30)
        
        # Create Page Containers
        self._setup_pages()

    def _load_sidebar_logo(self):
        try:
            ico_path = APP_ROOT / 'logo.ico'
            png_path = APP_ROOT / 'logo.png'
            img_path = ico_path if ico_path.exists() else (png_path if png_path.exists() else None)
            
            if img_path:
                img = Image.open(str(img_path)).convert("RGBA")
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(48, 48))
                logo_label = ctk.CTkLabel(self.sidebar, image=ctk_img, text="")
                logo_label.pack(pady=(40, 10))
            
            ctk.CTkLabel(self.sidebar, text="CLINIC MANAGER", 
                         font=make_font(Fonts.MD, "bold"),
                         text_color=Colors.PRIMARY).pack(pady=(0, 40))
        except Exception as e:
            log(f"Sidebar logo error: {e}", WORKSPACE / 'manager.log')

    def _setup_navigation(self):
        nav_data = [
            ("dashboard", "📊  Dashboard"),
            ("serverlog", "📋  Server Log"),
            ("settings",  "⚙️  Settings")
        ]
        
        for page_id, label in nav_data:
            btn = ctk.CTkButton(
                self.sidebar, text=label,
                height=45, corner_radius=8,
                fg_color="transparent",
                text_color=Colors.pair(Colors.TEXT_SECONDARY, Colors.DARK_TEXT_MUTED),
                hover_color=Colors.pair(Colors.SURFACE_ALT, Colors.DARK_SURFACE2),
                anchor="w", font=make_font(Fonts.SM, "bold"),
                command=lambda p=page_id: self.select_page(p)
            )
            btn.pack(fill="x", padx=15, pady=5)
            self.nav_buttons[page_id] = btn

    def _setup_pages(self):
        # 1. Dashboard Page
        self.pages["dashboard"] = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self._build_dashboard_page(self.pages["dashboard"])
        
        # 2. Server Log Page
        self.pages["serverlog"] = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self._build_log_page(self.pages["serverlog"])
        
        # 3. Settings Page
        self.pages["settings"] = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self._build_settings_page(self.pages["settings"])

    def _build_dashboard_page(self, parent):
        # Title
        ctk.CTkLabel(parent, text="Dashboard Overview", font=make_font(Fonts.XL, "bold"),
                     text_color=Colors.pair(Colors.TEXT_PRIMARY, Colors.DARK_TEXT)).pack(anchor="w", pady=(0, 30))
        
        # Control Bar
        ctrl_bar = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl_bar.pack(fill="x", pady=(0, 20))
        
        self.start_btn = PrimaryButton(ctrl_bar, text="▶  Start Server", command=self.threaded(self.start_server))
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = DangerButton(ctrl_bar, text="⏹  Stop Server", command=self.stop_server, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        self.browser_btn = GhostButton(ctrl_bar, text="🌐  Open Browser", command=self.open_browser, state="disabled")
        self.browser_btn.pack(side="left", padx=5)

        # Main Status Card
        self.status_card = ctk.CTkFrame(parent, fg_color=Colors.pair(Colors.SURFACE, Colors.DARK_SURFACE),
                            corner_radius=16, border_width=1, border_color=Colors.pair(Colors.BORDER, Colors.DARK_BORDER))
        self.status_card.pack(fill="x", pady=10)
        
        info_frame = ctk.CTkFrame(self.status_card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=25, pady=25)
        
        ctk.CTkLabel(info_frame, text="Network Connectivity", font=make_font(Fonts.LG, "bold")).pack(anchor="w")
        
        url_box = ctk.CTkFrame(info_frame, fg_color=Colors.pair(Colors.SURFACE_ALT, Colors.DARK_BG), corner_radius=8)
        url_box.pack(fill="x", pady=20)
        
        ctk.CTkLabel(url_box, textvariable=self.url_var, font=make_font(Fonts.MD, "bold"),
                     text_color=Colors.PRIMARY).pack(padx=20, pady=10)

        ctk.CTkLabel(info_frame, text="The server is available to any device on your local network. Scan the QR to connect.", 
                     font=make_font(Fonts.XS), text_color=Colors.TEXT_SECONDARY, wraplength=350, justify="left").pack(anchor="w")

        # Right side: QR Area (White Box)
        qr_container = ctk.CTkFrame(self.status_card, fg_color="#FFFFFF", corner_radius=12, width=180, height=180)
        qr_container.pack(side="right", padx=25, pady=25)
        qr_container.pack_propagate(False)

        # Canvas should fill the white box
        self.qr_canvas = ctk.CTkCanvas(qr_container, bg="white", highlightthickness=0)
        self.qr_canvas.pack(fill="both", expand=True, padx=5, pady=5)


    def _build_log_page(self, parent):
        ctk.CTkLabel(parent, text="System Activity Log", font=make_font(Fonts.XL, "bold"),
                     text_color=Colors.pair(Colors.TEXT_PRIMARY, Colors.DARK_TEXT)).pack(anchor="w", pady=(0, 20))
        
        log_frame = ctk.CTkFrame(parent, fg_color=Colors.pair(Colors.SURFACE, Colors.DARK_SURFACE),
                                 corner_radius=16, border_width=1, border_color=Colors.pair(Colors.BORDER, Colors.DARK_BORDER))
        log_frame.pack(fill="both", expand=True)
        
        self.output = ctk.CTkTextbox(log_frame, fg_color="transparent", font=make_font(Fonts.SM),
                                     text_color=Colors.pair(Colors.TEXT_PRIMARY, Colors.DARK_TEXT))
        self.output.pack(fill="both", expand=True, padx=10, pady=10)

    def _build_settings_page(self, parent):
        ctk.CTkLabel(parent, text="Application Settings", font=make_font(Fonts.XL, "bold"),
                     text_color=Colors.pair(Colors.TEXT_PRIMARY, Colors.DARK_TEXT)).pack(anchor="w", pady=(0, 30))
        
        settings_container = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        settings_container.pack(fill="both", expand=True)

        # 1. Appearance Section
        self._add_settings_header(settings_container, "🎨  Appearance")
        
        appearance_frame = self._add_settings_card(settings_container)
        ctk.CTkLabel(appearance_frame, text="System Theme", font=make_font(Fonts.SM, "bold")).pack(side="left", padx=20)
        
        theme_menu = ctk.CTkOptionMenu(appearance_frame, values=["Dark", "Light", "System"],
                                       command=lambda m: ctk.set_appearance_mode(m.lower()))
        theme_menu.pack(side="right", padx=20, pady=15)

        # 2. Server Config Section
        self._add_settings_header(settings_container, "🌐  Network Configuration")
        
        net_frame = self._add_settings_card(settings_container)
        ctk.CTkLabel(net_frame, text="Default Server Port", font=make_font(Fonts.SM, "bold")).pack(side="left", padx=20)
        
        port_entry = ctk.CTkEntry(net_frame, textvariable=self.port_var, width=100)
        port_entry.pack(side="right", padx=20, pady=15)

        # 3. Data Management Section
        self._add_settings_header(settings_container, "💾  Data Management")
        
        data_frame = self._add_settings_card(settings_container)
        ctk.CTkLabel(data_frame, text="Backup & Recovery", font=make_font(Fonts.SM, "bold")).pack(side="left", padx=20)
        
        btn_box = ctk.CTkFrame(data_frame, fg_color="transparent")
        btn_box.pack(side="right", padx=10)
        
        GhostButton(btn_box, text="Create Backup", command=self.threaded(lambda: backup_data(self.append_output))).pack(side="left", padx=5, pady=10)
        GhostButton(btn_box, text="Restore Data", command=self.threaded(lambda: restore_data(self.append_output))).pack(side="left", padx=5, pady=10)

    def _add_settings_header(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=make_font(Fonts.MD, "bold"),
                     text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(20, 10), padx=5)

    def _add_settings_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=Colors.pair(Colors.SURFACE, Colors.DARK_SURFACE),
                            corner_radius=12, border_width=1, border_color=Colors.pair(Colors.BORDER, Colors.DARK_BORDER))
        card.pack(fill="x", pady=5)
        return card

    def select_page(self, page_id):
        # Update Nav Buttons
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=Colors.PRIMARY, text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=Colors.pair(Colors.TEXT_SECONDARY, Colors.DARK_TEXT_MUTED))
        
        # Switch Page
        for pid, frame in self.pages.items():
            if pid == page_id:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    def threaded(self, fn):
        def wrapper(*a, **k):
            threading.Thread(target=fn, args=a, kwargs=k, daemon=True).start()
        return wrapper

    def append_output(self, text: str):
        self.output_queue.put(text)

    def process_output_queue(self):
        try:
            while True:
                text = self.output_queue.get_nowait()
                self.output.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
                self.output.see("end")
                log(text, WORKSPACE / 'manager.log')
        except queue.Empty:
            pass
        self.after(100, self.process_output_queue)

    def update_progress(self, value):
        if self.splash and self.splash.winfo_exists():
            self.splash.update_splash(percent=value)

    def update_splash(self, **kwargs):
        if self.splash and self.splash.winfo_exists():
            self.splash.update_splash(**kwargs)

    def startup_checks(self):
        try:
            self.append_output("System check initiated...")
            ensure_runtime_directories()
            
            self.update_splash(label_text="Checking Resources...", status_text="Step 1/5")
            required = get_required_setup_items()
            if any(not p.exists() for p in required):
                download_and_extract(get_required_setup_items, self.append_output, self.update_splash, self.update_progress, self.install_python_packages)

            self.update_splash(label_text="Validating Components...", status_text="Step 2/5")
            check_folders(self.append_output)

            self.update_splash(label_text="Setting up QR Service...", status_text="Step 3/5")
            ensure_qrcode(self.append_output)

            self.update_splash(label_text="Finalizing Environment...", status_text="Step 5/5")
            install_requirements(self.append_output)
            
            self.append_output("System ready.")
            self.after(500, self._finalize_startup)
        except Exception as e:
            self.append_output(f"Startup warning: {e}")
            self.after(1000, self._finalize_startup)

    def _finalize_startup(self):
        try:
            if self.splash:
                self.splash.destroy()
        except:
            pass
        self.deiconify()

    def start_server(self):
        if self.server_running: return
        
        port = self.port_var.get()
        while is_port_in_use(port): port += 1
        self.server_port = port
        
        try:
            cmd = get_server_command(port)
            env = os.environ.copy()
            env['CLINIC_DATA_DIR'] = str(DATA_DIR)
            env['CLINIC_STATIC_ROOT'] = str(get_runtime_static_dir())
            env['CLINIC_WORKSPACE'] = str(WORKSPACE)
            
            flags = 0x08000000 if sys.platform == "win32" else 0
            self.server_process = subprocess.Popen(cmd, creationflags=flags, env=env)
            self.server_running = True
            
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.browser_btn.configure(state="normal")
            
            ip = find_local_ip(self.append_output)
            self.current_ip = ip
            url = f"http://{ip}:{port}"
            self.url_var.set(url)
            
            generate_qr(self.qr_canvas, self.url_var.get(), self.append_output)
            self.append_output(f"✓ Server live at {self.url_var.get()}")
            
            threading.Thread(target=network_monitor, args=({
                'network_monitor_running': True, 'server_running': True,
                'last_ip_check_time': time.time(), 'current_ip': ip, 'server_port': port
            }, self.append_output, self.update_server_url_for_network_change), daemon=True).start()

            threading.Thread(target=self._monitor_server, daemon=True).start()
        except Exception as e:
            self.append_output(f"Failed to start: {e}")

    def _monitor_server(self):
        if self.server_process:
            self.server_process.wait()
            self.server_running = False
            self.after(0, self.on_server_stopped)

    def update_server_url_for_network_change(self, new_ip):
        new_url = f"http://{new_ip}:{self.server_port}"
        self.after(0, lambda: self.url_var.set(new_url))
        self.after(0, lambda: generate_qr(self.qr_canvas, new_url, self.append_output))

    def on_server_stopped(self):
        self.url_var.set("")
        self.qr_canvas.delete("all")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.browser_btn.configure(state="disabled")
        self.append_output("Server offline.")

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            kill_process_on_port(self.server_port, self.append_output)
            self.server_running = False
            self.on_server_stopped()

    def open_browser(self):
        import webbrowser
        webbrowser.open(f"http://localhost:{self.server_port}")

    def on_closing(self):
        self.stop_server()
        self.destroy()
        sys.exit(0)

    def install_python_packages(self, packages):
        return install_python_packages(packages, self.append_output)
