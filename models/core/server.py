import os
import sys
import subprocess
import socket
from pathlib import Path
from models.utils.os_helpers import is_frozen_build

def get_server_command(port: int):
    from models.config.settings import PROJECT_DIR, PYTHON_EXE
    manage_py = str(PROJECT_DIR / 'manage.py')
    if is_frozen_build():
        if PYTHON_EXE.exists() and Path(manage_py).exists():
            return [str(PYTHON_EXE), manage_py, 'runserver', f'0.0.0.0:{port}']
        return [str(sys.executable), '--run-django-server', str(port)]
    return [str(PYTHON_EXE), manage_py, 'runserver', f'0.0.0.0:{port}']

def run_embedded_django_server(port: int):
    from models.config.settings import PYTHON_EXE, WORKSPACE, get_project_dir, get_runtime_data_dir, get_runtime_static_dir
    from models.core.migration_manager import run_full_migration_pipeline, run_full_migration_pipeline_django_api

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
    os.environ.setdefault('CLINIC_WORKSPACE', str(WORKSPACE))

    if PYTHON_EXE.exists():
        python_exe = str(PYTHON_EXE)
        manage_script = str(project_dir / 'manage.py')

        # Build env for subprocess migration calls
        migration_env = os.environ.copy()
        migration_env.setdefault('DJANGO_SETTINGS_MODULE', 'clinic.settings')
        migration_env.setdefault('CLINIC_DATA_DIR', str(runtime_data_dir))
        migration_env.setdefault('CLINIC_STATIC_ROOT', str(runtime_static_dir))
        migration_env.setdefault('CLINIC_WORKSPACE', str(WORKSPACE))

        # Run migration pipeline: makemigrations app → migrate
        run_full_migration_pipeline(
            python_exe=python_exe,
            manage_script=manage_script,
            project_dir=project_dir,
            data_dir=runtime_data_dir,
            env=migration_env,
        )

        os.execv(python_exe, [python_exe, manage_script, 'runserver', f'0.0.0.0:{port}'])

    from django.core.management import execute_from_command_line

    # Run full migration pipeline via Django API (no external Python exe needed)
    run_full_migration_pipeline_django_api(
        project_dir=project_dir,
        data_dir=runtime_data_dir,
    )

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

def kill_process_on_port(port: int, logger_callback=None):
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
                            if logger_callback:
                                logger_callback(f'Killed process {pid} on port {port}')
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
                        if logger_callback:
                            logger_callback(f'Killed process {pid} on port {port}')
                    except Exception:
                        pass
    except Exception as e:
        if logger_callback:
            logger_callback(f'Error killing process on port {port}: {str(e)}')
