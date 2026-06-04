try:
    import customtkinter as ctk
except ImportError:
    ctk = None

class Fonts:
    FAMILY = "Segoe UI"
    
    XS = 11
    SM = 12
    MD = 14
    LG = 18
    XL = 24
    XXL = 32

def make_font(size: int, weight: str = "normal"):
    if not ctk:
        return ("Segoe UI", size, weight)
    return ctk.CTkFont(family=Fonts.FAMILY, size=size, weight=weight)
