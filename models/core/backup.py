import os
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from models.config.settings import DATA_DIR, WORKSPACE

def backup_data(append_output_callback):
    if not DATA_DIR.exists():
        append_output_callback('No data folder to backup')
        return
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    target = WORKSPACE / f'data-backup-{timestamp}.zip'
    append_output_callback(f'Creating backup {target}...')
    try:
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(DATA_DIR):
                for f in files:
                    full = Path(root) / f
                    arc = full.relative_to(WORKSPACE)
                    z.write(full, arc)
        append_output_callback('Backup complete: ' + str(target))
    except Exception as e:
        append_output_callback('Backup failed: ' + str(e))

def restore_data(append_output_callback):
    path = filedialog.askopenfilename(title='Select backup zip', filetypes=[('Zip files', '*.zip')])
    if not path:
        return
    append_output_callback('Restoring from ' + path)
    try:
        # remove existing data (keep safe: move to .old)
        if DATA_DIR.exists():
            old = WORKSPACE / f'data.old.{int(time.time())}'
            shutil.move(str(DATA_DIR), str(old))
            append_output_callback('Moved existing data to ' + str(old))
        with zipfile.ZipFile(path, 'r') as z:
            z.extractall(WORKSPACE)
        append_output_callback('Restore complete')
    except Exception as e:
        append_output_callback('Restore failed: ' + str(e))
