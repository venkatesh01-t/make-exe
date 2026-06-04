class Colors:
    # Core Branding
    PRIMARY        = "#3B82F6"  # Blue 500
    PRIMARY_HOVER  = "#2563EB"  # Blue 600
    
    # Backgrounds
    BG             = "#F8FAFC"  # Slate 50
    DARK_BG        = "#0F172A"  # Slate 900
    
    # Surface/Cards
    SURFACE        = "#FFFFFF"
    DARK_SURFACE   = "#1E293B"  # Slate 800
    SURFACE_ALT    = "#F1F5F9"  # Slate 100
    DARK_SURFACE2  = "#334155"  # Slate 700
    
    # Borders
    BORDER         = "#E2E8F0"  # Slate 200
    DARK_BORDER    = "#334155"  # Slate 700
    
    # Text
    TEXT_PRIMARY   = "#1E293B"  # Slate 800
    TEXT_SECONDARY = "#64748B"  # Slate 500
    TEXT_MUTED     = "#94A3B8"  # Slate 400
    DARK_TEXT      = "#F8FAFC"  # Slate 50
    DARK_TEXT_MUTED= "#94A3B8"  # Slate 400
    
    # Status
    SUCCESS        = "#10B981"  # Emerald 500
    DANGER         = "#EF4444"  # Red 500
    WARNING        = "#F59E0B"  # Amber 500
    INFO           = "#0EA5E9"  # Sky 500

    @staticmethod
    def pair(light: str, dark: str) -> tuple[str, str]:
        """Utility for ctk color tuples."""
        return (light, dark)
