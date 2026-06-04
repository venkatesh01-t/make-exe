import customtkinter as ctk
from tkinter import ttk
from pathlib import Path
from models.config.settings import APP_ROOT
from models.utils.os_helpers import apply_window_icon, log
from models.design_system.tokens import Colors
from models.design_system.fonts import make_font, Fonts

def calculate_splash_geometry(root, base_w=500, base_h=550):
    """Return a geometry string for a responsive splash centered on screen."""
    try:
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        width = max(380, min(base_w, int(screen_w * 0.45)))
        height = max(500, min(base_h, int(screen_h * 0.60)))
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        return f'{width}x{height}+{x}+{y}'
    except Exception:
        return f'{base_w}x{base_h}'

class SplashScreen(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Clinic Manager")
        apply_window_icon(self, APP_ROOT)
        self.resizable(False, False)
        self.configure(fg_color=Colors.pair(Colors.BG, Colors.DARK_BG))

        # Hide title bar for a modern splash look
        self.overrideredirect(True)

        # Responsive splash geometry
        try:
            geom = calculate_splash_geometry(parent)
            self.geometry(geom)
        except Exception:
            self.geometry('500x550')

        # Splash header
        header_frame = ctk.CTkFrame(self, fg_color=Colors.pair(Colors.SURFACE, Colors.DARK_SURFACE), height=80, corner_radius=0)
        header_frame.pack(side='top', fill='x')
        header_frame.pack_propagate(False)
        
        ctk.CTkLabel(header_frame, text='CLINIC MANAGER', 
                     font=make_font(Fonts.XL, "bold"),
                     text_color=Colors.pair(Colors.TEXT_PRIMARY, Colors.DARK_TEXT)).pack(expand=True)

        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(expand=True, fill='both', pady=(20, 10))

        # Try to load a logo for the splash
        self._splash_image = None
        TARGET_LOGO_SIZE = (160, 160)
        try:
            ico_path = APP_ROOT / 'logo.ico'
            png_path = APP_ROOT / 'logo.png'
            
            from PIL import Image
            img_path = None
            if ico_path.exists():
                img_path = ico_path
            elif png_path.exists():
                img_path = png_path

            if img_path:
                img = Image.open(str(img_path)).convert("RGBA")
                # Use CTkImage for HighDPI scaling support
                self._splash_image = ctk.CTkImage(light_image=img, dark_image=img, size=TARGET_LOGO_SIZE)
        except Exception as e:
            log(f'Failed to load splash logo: {e}', APP_ROOT / 'clinic_manager_data' / 'manager.log')

        if self._splash_image:
            logo_label = ctk.CTkLabel(content_frame, image=self._splash_image, text="")
            logo_label.pack(pady=10)
        else:
            ctk.CTkLabel(content_frame, text='🏥', font=make_font(48)).pack(pady=10)

        self.splash_label = ctk.CTkLabel(content_frame, text='Initializing system...\nPlease wait',
                                         font=make_font(Fonts.MD), 
                                         text_color=Colors.pair(Colors.TEXT_PRIMARY, Colors.DARK_TEXT))
        self.splash_label.pack(pady=15)

        # Progress bar
        progress_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        progress_frame.pack(fill='x', pady=5, padx=50) 
        
        self.splash_progress = ctk.CTkProgressBar(progress_frame, 
                                                  fg_color=Colors.pair(Colors.BORDER, Colors.DARK_BORDER),
                                                  progress_color=Colors.PRIMARY,
                                                  height=10)
        self.splash_progress.pack(fill='x')
        self.splash_progress.set(0)

        self.splash_percent = ctk.CTkLabel(content_frame, text='0%', font=make_font(Fonts.XS),
                                           text_color=Colors.TEXT_SECONDARY)
        self.splash_percent.pack(pady=5)

        self.splash_status = ctk.CTkLabel(content_frame, text='', font=make_font(Fonts.XS),
                                          text_color=Colors.TEXT_SECONDARY)
        self.splash_status.pack(pady=2)

        footer_frame = ctk.CTkFrame(self, fg_color=Colors.pair(Colors.SURFACE_ALT, Colors.DARK_SURFACE2), height=40, corner_radius=0)
        footer_frame.pack(side='bottom', fill='x')
        footer_frame.pack_propagate(False)
        
        ctk.CTkLabel(footer_frame, text='© 2026 Clinic Solutions Inc.', font=make_font(Fonts.XS),
                     text_color=Colors.TEXT_SECONDARY).pack(expand=True)

        self.update()
        self.lift()
        self.attributes('-topmost', True)

    def update_splash(self, label_text=None, status_text=None, percent=None, stats_text=None, speed_text=None):
        if not self.winfo_exists():
            return

        try:
            if label_text is not None:
                self.splash_label.configure(text=label_text)
            if status_text is not None:
                self.splash_status.configure(text=status_text)
            if percent is not None:
                self.splash_progress.set(percent / 100)
                self.splash_percent.configure(text=f'{percent:.1f}%')
            
            self.update_idletasks()
        except Exception:
            pass
