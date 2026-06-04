try:
    import qrcode
except ImportError:
    qrcode = None

import customtkinter as ctk
from models.design_system.tokens import Colors
from models.design_system.fonts import make_font, Fonts

def generate_qr(canvas, text, append_output_callback):
    """Generate and draw QR code on canvas using fallback matrix drawing (no Pillow needed)."""
    global qrcode
    if qrcode is None:
        try:
            import qrcode as _q
            qrcode = _q
        except ImportError:
            append_output_callback('qrcode display unavailable')
            return

    try:
        # Clear canvas
        canvas.delete('all')
        
        # Generate QR matrix
        qr_obj = qrcode.QRCode(border=2)
        qr_obj.add_data(text)
        qr_obj.make(fit=True)
        matrix = qr_obj.get_matrix()
        
        rows = len(matrix)
        cols = len(matrix[0]) if rows else 0
        if rows == 0 or cols == 0:
            return
        
        # Draw QR on canvas
        canvas_width = float(canvas.winfo_width()) if canvas.winfo_width() > 1 else float(canvas.cget("width"))
        canvas_height = float(canvas.winfo_height()) if canvas.winfo_height() > 1 else float(canvas.cget("height"))
        
        # Ensure we have valid dimensions
        if canvas_width <= 1: canvas_width = 180
        if canvas_height <= 1: canvas_height = 180

        padding = 8
        usable_size = min(canvas_width, canvas_height) - 2 * padding
        px = usable_size / max(rows, cols)
        
        offset_x = (canvas_width - (px * cols)) / 2
        offset_y = (canvas_height - (px * rows)) / 2
        
        for r in range(rows):
            for c in range(cols):
                if matrix[r][c]:
                    x0 = offset_x + c * px
                    y0 = offset_y + r * px
                    x1 = x0 + px
                    y1 = y0 + px
                    canvas.create_rectangle(x0, y0, x1, y1, fill='black', outline='')
        
        append_output_callback('QR code generated successfully')
    except Exception as e:
        append_output_callback('QR generation failed: ' + str(e))

class SkeletonFrame(ctk.CTkFrame):
    """Animated shimmer skeleton loader using color pulsing."""

    def __init__(self, master, width: int = 200, height: int = 20,
                 corner_radius: int = 8, **kw):
        super().__init__(
            master, width=width, height=height,
            corner_radius=corner_radius,
            fg_color=Colors.pair(Colors.BORDER, Colors.DARK_BORDER),
            **kw
        )
        self.pack_propagate(False)
        self._shimmer = False
        self._step    = 0
        self._colors_lt = ["#E2E8F0", "#F1F5F9", "#E2E8F0", "#CBD5E1", "#E2E8F0"]
        self._colors_dk = ["#334155", "#475569", "#334155", "#1E293B", "#334155"]
        self._start_shimmer()

    def _start_shimmer(self):
        self._shimmer = True
        self._tick()

    def _tick(self):
        if not self._shimmer:
            return
        mode = ctk.get_appearance_mode().lower()
        colors = self._colors_lt if mode == "light" else self._colors_dk
        c = colors[self._step % len(colors)]
        try:
            self.configure(fg_color=c)
        except Exception:
            return
        self._step += 1
        self.after(120, self._tick)

    def stop(self):
        self._shimmer = False

class GhostButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        super().__init__(
            master,
            fg_color="transparent",
            text_color=Colors.pair(Colors.TEXT_SECONDARY, Colors.DARK_TEXT_MUTED),
            hover_color=Colors.pair(Colors.SURFACE_ALT, Colors.DARK_SURFACE2),
            font=make_font(Fonts.SM, "bold"),
            **kw
        )

class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        super().__init__(
            master,
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_HOVER,
            text_color="#FFFFFF",
            font=make_font(Fonts.SM, "bold"),
            **kw
        )

class DangerButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        super().__init__(
            master,
            fg_color=Colors.DANGER,
            hover_color="#DC2626", # Red 600
            text_color="#FFFFFF",
            font=make_font(Fonts.SM, "bold"),
            **kw
        )
