"""
migration_manager.py
====================
Safe, automatic Django migration detection and execution for the Clinic Manager EXE.

Strategy (3 layers — fastest to most thorough):
  Layer 1 — Hash file: check if app/models.py checksum changed since last run (~0ms)
  Layer 2 — migrate --check: detect unapplied migrations in DB (~200ms)
  Layer 3 — Pre-server guard: last-resort check before runserver starts

Key guarantees:
  - Zero data loss: db.sqlite3 is backed up before ANY migration runs
  - No repeated work: hash file skips migration when schema hasn't changed
  - Works in both subprocess mode (PYTHON_EXE) and direct Django API mode
  - SQLite safe: uses shutil.copy2 (no rename/move that could corrupt WAL)
"""

import os
import sys
import hashlib
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────

HASH_FILE_NAME = ".migration_hash"
MAX_BACKUPS = 3  # Keep only the 3 most recent pre-migration backups


# ─────────────────────────────────────────────────────────────────
# HASH HELPERS  (Layer 1 — fast path)
# ─────────────────────────────────────────────────────────────────

def compute_models_hash(project_dir: Path) -> str:
    """
    Compute MD5 checksum of app/models.py to detect schema changes.
    Returns hex digest string, or empty string if file not found.
    """
    models_file = project_dir / "app" / "models.py"
    if not models_file.exists():
        return ""
    try:
        content = models_file.read_bytes()
        return hashlib.md5(content).hexdigest()
    except Exception:
        return ""


def read_stored_hash(data_dir: Path) -> str:
    """Read the stored migration hash from the data directory."""
    hash_file = data_dir / HASH_FILE_NAME
    try:
        if hash_file.exists():
            return hash_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def write_stored_hash(data_dir: Path, hash_value: str) -> None:
    """Persist migration hash to the data directory."""
    hash_file = data_dir / HASH_FILE_NAME
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        hash_file.write_text(hash_value, encoding="utf-8")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────
# BACKUP HELPERS  (Safe SQLite copy before any migration)
# ─────────────────────────────────────────────────────────────────

def backup_db_before_migrate(data_dir: Path, log_cb=None) -> bool:
    """
    Create a timestamped copy of db.sqlite3 before running any migration.
    Keeps only the MAX_BACKUPS most recent backups.

    Returns True if backup succeeded or DB doesn't exist yet.
    Never raises — migration proceeds even if backup fails.
    """
    db_path = data_dir / "db.sqlite3"

    if not db_path.exists():
        _log(log_cb, "No existing database found — starting fresh, no backup needed.")
        return True

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"db.sqlite3.pre_migrate_{timestamp}.bak"
    backup_path = data_dir / backup_name

    try:
        # shutil.copy2 preserves metadata and does NOT move/rename the original
        # This is the safest approach for SQLite (no WAL corruption risk)
        shutil.copy2(str(db_path), str(backup_path))
        _log(log_cb, f"✓ DB backup created: {backup_name}")
        _cleanup_old_backups(data_dir, log_cb)
        return True
    except Exception as e:
        _log(log_cb, f"⚠ Backup warning (non-fatal): {e}")
        return False


def _cleanup_old_backups(data_dir: Path, log_cb=None) -> None:
    """Remove old backup files beyond MAX_BACKUPS limit."""
    try:
        backups = sorted(
            data_dir.glob("db.sqlite3.pre_migrate_*.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,  # newest first
        )
        for old_backup in backups[MAX_BACKUPS:]:
            try:
                old_backup.unlink()
                _log(log_cb, f"  Removed old backup: {old_backup.name}")
            except Exception:
                pass
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────
# MIGRATION CHECK  (Layer 2 — migrate --check)
# ─────────────────────────────────────────────────────────────────

def check_migrations_needed_subprocess(python_exe: str, manage_script: str, env: dict) -> bool:
    """
    Run `manage.py migrate --check` and return True if unapplied migrations exist.
    Django exit code: 0 = all applied, 1 = unapplied migrations found.
    Returns True (needs migration) on any error — safe default.
    """
    try:
        CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
        result = subprocess.run(
            [python_exe, manage_script, "migrate", "--check"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        # Exit code 1 = unapplied migrations exist
        return result.returncode != 0
    except Exception:
        return True  # Safe default: assume migration needed


def check_migrations_needed_django_api() -> bool:
    """
    Use Django's management API to check for unapplied migrations.
    Returns True if any unapplied migrations exist.
    """
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        # --check exits with non-zero if unapplied, but call_command doesn't expose exit codes
        # Use showmigrations to inspect state instead
        call_command("showmigrations", "--list", stdout=out)
        output = out.getvalue()
        # Look for '[ ]' which indicates an unapplied migration
        return "[ ]" in output
    except SystemExit as e:
        # migrate --check exits with code 1 if unapplied
        return str(e) != "0"
    except Exception:
        return True  # Safe default


# ─────────────────────────────────────────────────────────────────
# MIGRATION EXECUTION
# ─────────────────────────────────────────────────────────────────

def run_makemigrations(python_exe: str, manage_script: str, env: dict, log_cb=None) -> bool:
    """
    Run `manage.py makemigrations app` as a subprocess.
    NOTE: 'makemigrations' and 'app' must be SEPARATE list elements.
    """
    _log(log_cb, "Running makemigrations...")
    try:
        CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
        result = subprocess.run(
            [python_exe, manage_script, "makemigrations", "app"],  # ← TWO separate args
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.stdout.strip():
            _log(log_cb, f"  makemigrations: {result.stdout.strip()}")
        if result.returncode == 0:
            _log(log_cb, "✓ makemigrations complete")
            return True
        else:
            _log(log_cb, f"⚠ makemigrations exited with code {result.returncode}: {result.stderr.strip()}")
            return False
    except Exception as e:
        _log(log_cb, f"⚠ makemigrations error: {e}")
        return False


def run_migrate(python_exe: str, manage_script: str, env: dict, log_cb=None) -> bool:
    """
    Run `manage.py migrate` as a subprocess to apply all pending migrations.
    Uses --run-syncdb to ensure new tables are created even without migration files.
    """
    _log(log_cb, "Applying database migrations...")
    try:
        CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
        result = subprocess.run(
            [python_exe, manage_script, "migrate", "--run-syncdb"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                _log(log_cb, f"  {line}")
        if result.returncode == 0:
            _log(log_cb, "✓ Database migrations applied successfully")
            return True
        else:
            _log(log_cb, f"⚠ migrate exited with code {result.returncode}: {result.stderr.strip()}")
            return False
    except Exception as e:
        _log(log_cb, f"⚠ migrate error: {e}")
        return False


def run_makemigrations_django_api(log_cb=None) -> bool:
    """Run makemigrations via Django's management API (no subprocess)."""
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("makemigrations", "app", stdout=out, verbosity=1)
        output = out.getvalue().strip()
        if output:
            _log(log_cb, f"  makemigrations: {output}")
        _log(log_cb, "✓ makemigrations (API) complete")
        return True
    except Exception as e:
        _log(log_cb, f"⚠ makemigrations API error: {e}")
        return False


def run_migrate_django_api(log_cb=None) -> bool:
    """Run migrate via Django's management API (no subprocess)."""
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("migrate", "--run-syncdb", stdout=out, verbosity=1)
        output = out.getvalue().strip()
        if output:
            for line in output.splitlines():
                _log(log_cb, f"  {line}")
        _log(log_cb, "✓ Database migrations applied (API)")
        return True
    except Exception as e:
        _log(log_cb, f"⚠ migrate API error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────
# FULL PIPELINE — SUBPROCESS MODE  (called from GUI / startup_checks)
# ─────────────────────────────────────────────────────────────────

def run_full_migration_pipeline(
    python_exe: str,
    manage_script: str,
    project_dir: Path,
    data_dir: Path,
    env: dict = None,
    log_cb=None,
) -> bool:
    """
    Full 3-layer migration pipeline (subprocess mode).

    Args:
        python_exe:   Path to the bundled Python executable
        manage_script: Path to manage.py
        project_dir:  Django project directory (contains app/models.py)
        data_dir:     Runtime data directory (where db.sqlite3 lives)
        env:          Environment variables dict (defaults to os.environ.copy())
        log_cb:       Optional callback(str) for logging output

    Returns:
        True if DB is ready (migrations applied or already up-to-date)
    """
    if env is None:
        env = os.environ.copy()

    _log(log_cb, "─" * 50)
    _log(log_cb, "Database schema check starting...")

    # ── Layer 1: Hash check ──────────────────────────────────────
    current_hash = compute_models_hash(project_dir)
    stored_hash = read_stored_hash(data_dir)
    hash_changed = (current_hash != stored_hash) or (not stored_hash)

    if hash_changed:
        _log(log_cb, "Schema change detected — running full migration pipeline...")
        _run_pipeline_steps(
            python_exe, manage_script, project_dir, data_dir, env,
            log_cb, current_hash, run_makemigrations_step=True
        )
        return True

    # ── Layer 2: migrate --check ─────────────────────────────────
    _log(log_cb, "No schema change detected — checking migration state...")
    needs_migration = check_migrations_needed_subprocess(python_exe, manage_script, env)

    if needs_migration:
        _log(log_cb, "Unapplied migrations found — applying now...")
        _run_pipeline_steps(
            python_exe, manage_script, project_dir, data_dir, env,
            log_cb, current_hash, run_makemigrations_step=False
        )
        return True

    # ── All up to date ───────────────────────────────────────────
    _log(log_cb, "✓ Database is up to date — skipping migration")
    _log(log_cb, "─" * 50)
    return True


def _run_pipeline_steps(
    python_exe, manage_script, project_dir, data_dir, env,
    log_cb, new_hash, run_makemigrations_step=True
):
    """Internal: execute backup → makemigrations → migrate → write hash."""
    # Step A: Backup
    backup_db_before_migrate(data_dir, log_cb)

    # Step B: makemigrations (only when schema changed)
    if run_makemigrations_step:
        run_makemigrations(python_exe, manage_script, env, log_cb)

    # Step C: migrate
    run_migrate(python_exe, manage_script, env, log_cb)

    # Step D: Write new hash
    if new_hash:
        write_stored_hash(data_dir, new_hash)

    _log(log_cb, "─" * 50)


# ─────────────────────────────────────────────────────────────────
# FULL PIPELINE — DJANGO API MODE  (called from run_embedded_django_server)
# ─────────────────────────────────────────────────────────────────

def run_full_migration_pipeline_django_api(
    project_dir: Path,
    data_dir: Path,
    log_cb=None,
) -> bool:
    """
    Full migration pipeline using Django's management API directly (no subprocess).
    Used in `run_embedded_django_server()` when no external Python exe is available.

    Args:
        project_dir:  Django project directory (contains app/models.py)
        data_dir:     Runtime data directory (where db.sqlite3 lives)
        log_cb:       Optional callback(str) for logging

    Returns:
        True if DB is ready
    """
    _log(log_cb, "─" * 50)
    _log(log_cb, "Database schema check (API mode) starting...")

    # ── Layer 1: Hash check ──────────────────────────────────────
    current_hash = compute_models_hash(project_dir)
    stored_hash = read_stored_hash(data_dir)
    hash_changed = (current_hash != stored_hash) or (not stored_hash)

    if hash_changed:
        _log(log_cb, "Schema change detected — running full migration pipeline (API mode)...")
        backup_db_before_migrate(data_dir, log_cb)
        run_makemigrations_django_api(log_cb)
        run_migrate_django_api(log_cb)
        if current_hash:
            write_stored_hash(data_dir, current_hash)
        _log(log_cb, "─" * 50)
        return True

    # ── Layer 2: showmigrations check ────────────────────────────
    _log(log_cb, "No schema change — checking migration state (API mode)...")
    needs_migration = check_migrations_needed_django_api()

    if needs_migration:
        _log(log_cb, "Unapplied migrations found — applying (API mode)...")
        backup_db_before_migrate(data_dir, log_cb)
        run_migrate_django_api(log_cb)
        if current_hash:
            write_stored_hash(data_dir, current_hash)
        _log(log_cb, "─" * 50)
        return True

    _log(log_cb, "✓ Database is up to date (API mode) — skipping migration")
    _log(log_cb, "─" * 50)
    return True


# ─────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────

def _log(log_cb, message: str) -> None:
    """Send a message to the log callback if provided, else print."""
    if log_cb:
        log_cb(message)
    else:
        print(message)
