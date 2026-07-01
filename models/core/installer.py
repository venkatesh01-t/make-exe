import os
import sys
import subprocess
from pathlib import Path
from models.config.settings import WORKSPACE, DATA_DIR, PYTHON_EXE, APP_ROOT, get_runtime_static_dir
from models.utils.os_helpers import is_frozen_build

def ensure_runtime_directories():
    paths = [WORKSPACE, DATA_DIR]
    if not is_frozen_build():
        paths.append(get_runtime_static_dir())

    for path in paths:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

def get_required_setup_items():
    items = [WORKSPACE / '3.11.9', WORKSPACE / 'data']
    if not is_frozen_build():
        items.append(WORKSPACE / 'clinic')
    return items

def check_folders(append_output_callback):
    expected = get_required_setup_items()
    missing = [str(path) for path in expected if not path.exists()]
    if missing:
        append_output_callback('Missing folders: ' + ', '.join(missing))
    else:
        append_output_callback('All expected folders present')
    return missing

def install_python_packages(packages, append_output_callback):
    """Install pip packages using bundled Python."""
    if not PYTHON_EXE.exists():
        append_output_callback(f'Python not found at {PYTHON_EXE}')
        return False
    cmd = [str(PYTHON_EXE), '-m', 'pip', 'install'] + packages
    append_output_callback('Installing packages: ' + ' '.join(packages))
    try:
        CREATE_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, creationflags=CREATE_NO_WINDOW)
        if proc.stdout:
            append_output_callback(proc.stdout)
        if proc.stderr:
            append_output_callback(proc.stderr)
        return proc.returncode == 0
    except Exception as e:
        append_output_callback('Package install failed: ' + str(e))
        return False

def install_requirements(append_output_callback):
    """Install all packages from the hardcoded requirements list (no requirements.txt needed)."""
    requirements = [
        'django==5.2.11',
        'opencv-python',
        'pillow',
    ]

    if not PYTHON_EXE.exists():
        append_output_callback(f'Python not found at {PYTHON_EXE}')
        return False

    append_output_callback(f'Installing requirements: {requirements}')
    cmd = [str(PYTHON_EXE), '-m', 'pip', 'install'] + requirements
    try:
        CREATE_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=CREATE_NO_WINDOW)
        if proc.stdout:
            append_output_callback(proc.stdout)
        if proc.stderr and proc.returncode != 0:
            append_output_callback('Errors: ' + proc.stderr)
        if proc.returncode == 0:
            append_output_callback('Requirements installed successfully')
            return True
        else:
            append_output_callback('Some requirements may have failed to install')
            return False
    except Exception as e:
        append_output_callback('Requirements install failed: ' + str(e))
        return False

def ensure_qrcode(append_output_callback):
    """Ensure qrcode package is installed."""
    try:
        import qrcode
        append_output_callback('qrcode already available')
        return True
    except ImportError:
        pass

    if is_frozen_build():
        append_output_callback('Frozen build detected, qrcode must be bundled at build time')
        return False
    
    append_output_callback('Installing qrcode package...')
    ok = install_python_packages(['qrcode[pil]'], append_output_callback)
    if not ok:
        append_output_callback('Failed to install qrcode; will attempt fallback rendering')
        return False
    
    try:
        import qrcode
        append_output_callback('qrcode imported successfully')
        return True
    except Exception as e:
        append_output_callback('qrcode import failed: ' + str(e))
        return False
