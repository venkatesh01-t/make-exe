"""
start_clinic_server.py — Waitress Production Server for Clinic Manager
=======================================================================
Usage:
    python start_clinic_server.py

Windows Startup:
    Double-click OR add to Task Scheduler / Startup folder

For mobile hotspot:
    Devices connect to: http://192.168.137.1:8000
    Local access:       http://127.0.0.1:8000
"""

import os
import sys
from pathlib import Path

# ─── Paths — set relative to this script ─────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_DIR  = SCRIPT_DIR / 'clinic_manager_data' / 'clinic'
DATA_DIR     = SCRIPT_DIR / 'clinic_manager_data' / 'data'
STATIC_DIR   = PROJECT_DIR / 'staticfiles'

# ─── Environment variables ────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clinic.settings')
os.environ.setdefault('CLINIC_DATA_DIR',        str(DATA_DIR))
os.environ.setdefault('CLINIC_STATIC_ROOT',     str(STATIC_DIR))
# Optional: set a real secret key
# os.environ.setdefault('DJANGO_SECRET_KEY', 'your-production-secret-key')

# ─── Add project to Python path ───────────────────────────────────────────────
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR.parent))

# ─── Ensure directories exist ────────────────────────────────────────────────
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'media').mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# ─── Bootstrap Django ─────────────────────────────────────────────────────────
import django
django.setup()

# ─── Run migrations (safe — only applies new ones) ────────────────────────────
from django.core.management import call_command

print("  Checking database migrations...")
try:
    call_command('migrate', '--run-syncdb', verbosity=1)
    print("  Migrations OK")
except Exception as e:
    print(f"  Migration warning: {e}")

# ─── Collect static files ─────────────────────────────────────────────────────
print("  Collecting static files...")
try:
    call_command('collectstatic', '--noinput', verbosity=0)
    print("  Static files collected")
except Exception as e:
    print(f"  Static files warning: {e}")

# ─── Waitress configuration ───────────────────────────────────────────────────
HOST    = '0.0.0.0'   # Listen on ALL interfaces (localhost + hotspot)
PORT    = 8000
THREADS = 8            # Handles 8 simultaneous device requests

# ─── Print access info ────────────────────────────────────────────────────────
print()
print("=" * 55)
print("  Clinic Manager — Production Server (Waitress)")
print("=" * 55)
print(f"  Hotspot URL :  http://192.168.137.1:{PORT}")
print(f"  Local URL   :  http://127.0.0.1:{PORT}")
print(f"  Threads     :  {THREADS}")
print(f"  Database    :  {DATA_DIR / 'db.sqlite3'}")
print(f"  Static Root :  {STATIC_DIR}")
print("=" * 55)
print("  Press Ctrl+C to stop the server")
print()

# ─── Start Waitress ───────────────────────────────────────────────────────────
from waitress import serve
from clinic.wsgi import application

serve(
    application,
    host=HOST,
    port=PORT,
    threads=THREADS,
    channel_timeout=60,
    cleanup_interval=10,
    connection_limit=300,
    trusted_proxy=None,
    clear_untrusted_proxy_headers=True,
)
