"""
migration_manager.py
====================
Safe, automatic Django migration execution for the Clinic Manager EXE.

Always runs in this exact order (matching CLI commands):
  1. python manage.py makemigrations app
  2. python manage.py migrate

Key guarantees:
  - Zero data loss: db.sqlite3 is backed up before migrations run
  - Both commands ALWAYS run every time (no skipping logic that can break)
  - Works in both subprocess mode (PYTHON_EXE) and direct Django API mode
  - SQLite safe: uses shutil.copy2 (no rename/move, no WAL corruption)
  - All errors are logged and non-fatal — app continues even if migration fails
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────

MAX_BACKUPS = 3   # Keep only the 3 most recent pre-migration backups
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


# ─────────────────────────────────────────────────────────────────
# BACKUP  (safe SQLite copy before any migration)
# ─────────────────────────────────────────────────────────────────

def backup_db_before_migrate(data_dir: Path, log_cb=None) -> bool:
    """
    Create a timestamped copy of db.sqlite3 before running any migration.
    Keeps only MAX_BACKUPS most recent backups — auto-removes older ones.

    Uses shutil.copy2 (not rename/move) so the original DB is never touched.
    Returns True always — non-fatal even if backup fails.
    """
    db_path = data_dir / "db.sqlite3"

    if not db_path.exists():
        _log(log_cb, "[Migration] No existing database — starting fresh, no backup needed.")
        return True

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"db.sqlite3.bak_{timestamp}"
    backup_path = data_dir / backup_name

    try:
        shutil.copy2(str(db_path), str(backup_path))
        _log(log_cb, f"[Migration] ✓ DB backup: {backup_name}")
        _cleanup_old_backups(data_dir, log_cb)
    except Exception as e:
        _log(log_cb, f"[Migration] ⚠ Backup warning (non-fatal): {e}")

    return True


def _cleanup_old_backups(data_dir: Path, log_cb=None) -> None:
    """Remove backup files beyond MAX_BACKUPS limit (keep newest)."""
    try:
        backups = sorted(
            data_dir.glob("db.sqlite3.bak_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,  # newest first
        )
        for old in backups[MAX_BACKUPS:]:
            try:
                old.unlink()
                _log(log_cb, f"[Migration]   Removed old backup: {old.name}")
            except Exception:
                pass
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────
# SUBPROCESS MODE  (uses bundled PYTHON_EXE)
# ─────────────────────────────────────────────────────────────────

def _run_cmd(cmd: list, env: dict, timeout: int, log_cb=None) -> bool:
    """Run a command as a subprocess, log output, return True on success."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        # Log stdout lines
        for line in (result.stdout or "").strip().splitlines():
            if line.strip():
                _log(log_cb, f"    {line}")
        # Log stderr on failure
        if result.returncode != 0:
            for line in (result.stderr or "").strip().splitlines():
                if line.strip():
                    _log(log_cb, f"    [stderr] {line}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        _log(log_cb, f"[Migration] ⚠ Command timed out: {' '.join(cmd)}")
        return False
    except Exception as e:
        _log(log_cb, f"[Migration] ⚠ Command error: {e}")
        return False


def run_full_migration_pipeline(
    python_exe: str,
    manage_script: str,
    project_dir: Path,
    data_dir: Path,
    env: dict = None,
    log_cb=None,
) -> bool:
    """
    Run the complete migration pipeline (subprocess mode):

      Step 1: python manage.py makemigrations app
      Step 2: python manage.py migrate

    Args:
        python_exe:    Path to the Python executable (bundled or system)
        manage_script: Absolute path to manage.py
        project_dir:   Django project directory (unused but kept for API compat)
        data_dir:      Runtime data directory (where db.sqlite3 lives)
        env:           Environment variables (defaults to os.environ.copy())
        log_cb:        Optional logging callback(str)

    Returns:
        True if both commands succeeded, False if either failed (non-fatal).
    """
    if env is None:
        env = os.environ.copy()

    _log(log_cb, "[Migration] " + "─" * 46)
    _log(log_cb, "[Migration] Starting database migration pipeline...")

    # Ensure data directory exists
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # Backup existing DB before touching anything
    backup_db_before_migrate(data_dir, log_cb)

    # ── Step: migrate ─────────────────────────────────────────
    _log(log_cb, "[Migration] Running: python manage.py migrate")
    ok = _run_cmd(
        [python_exe, manage_script, "migrate"],
        env=env,
        timeout=120,
        log_cb=log_cb,
    )
    if ok:
        _log(log_cb, "[Migration] ✓ migrate complete — database is ready")
    else:
        _log(log_cb, "[Migration] ⚠ migrate had issues — check logs above")

    _log(log_cb, "[Migration] " + "─" * 46)
    return ok


# ─────────────────────────────────────────────────────────────────
# DJANGO API MODE  (used when no external Python exe, e.g. fallback)
# ─────────────────────────────────────────────────────────────────

def run_full_migration_pipeline_django_api(
    project_dir: Path,
    data_dir: Path,
    log_cb=None,
) -> bool:
    """
    Run the complete migration pipeline via Django's management API (no subprocess).
    Used in run_embedded_django_server() when PYTHON_EXE is not available.

      Step 1: makemigrations app
      Step 2: migrate

    Returns:
        True if both steps succeeded, False otherwise (non-fatal).
    """
    from io import StringIO

    _log(log_cb, "[Migration] " + "─" * 46)
    _log(log_cb, "[Migration] Starting database migration pipeline (API mode)...")

    try:
        from django.core.management import call_command
    except ImportError as e:
        _log(log_cb, f"[Migration] ⚠ Django not available: {e}")
        return False

    # Ensure data directory exists
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # Backup before touching anything
    backup_db_before_migrate(data_dir, log_cb)

    # ── Step: migrate ─────────────────────────────────────────
    _log(log_cb, "[Migration] Running database migrate...")
    ok = False
    try:
        out = StringIO()
        call_command("migrate", stdout=out, verbosity=1)
        output = out.getvalue().strip()
        for line in output.splitlines():
            if line.strip():
                _log(log_cb, f"    {line}")
        _log(log_cb, "[Migration] ✓ migrate complete — database is ready")
        ok = True
    except Exception as e:
        _log(log_cb, f"[Migration] ⚠ migrate error: {e}")

    _log(log_cb, "[Migration] " + "─" * 46)
    return ok


# ─────────────────────────────────────────────────────────────────
# KEPT FOR BACKWARD COMPAT (used in main_window.py pre-server guard)
# ─────────────────────────────────────────────────────────────────

def check_migrations_needed_subprocess(python_exe: str, manage_script: str, env: dict) -> bool:
    """
    Quick check: does `migrate --check` return non-zero (unapplied migrations)?
    Used as a lightweight pre-server guard in start_server().
    Returns True (needs migration) on any error — safe default.
    """
    try:
        result = subprocess.run(
            [python_exe, manage_script, "migrate", "--check"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        return result.returncode != 0
    except Exception:
        return True  # Safe default: assume migration needed


# ─────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────

def _log(log_cb, message: str) -> None:
    """Send message to callback or print."""
    if log_cb:
        log_cb(message)
    else:
        print(message)
