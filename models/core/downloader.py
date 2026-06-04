import os
import shutil
import time
import zipfile
from pathlib import Path
from datetime import timedelta
import requests
from models.config.settings import WORKSPACE
from models.utils.os_helpers import sys

def download_and_extract(required_items_callback, append_output_callback, update_splash_callback, update_progress_callback, install_packages_callback):
    """Download and extract repo from GitHub if not already present."""
    # Check if required source folders already exist.
    if all(path.exists() for path in required_items_callback()):
        append_output_callback('Required setup items already present, skipping download')
        return True
    
    append_output_callback('Clinic folder not found, attempting download...')
    
    url = 'https://github.com/venkatesh01-t/getdownload/archive/refs/heads/main.zip'
    dest_zip = WORKSPACE / 'repo.zip'
    append_output_callback('Downloading repo from GitHub...')
    try:
        # Download with progress tracking
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()
        last_update_time = start_time
        last_downloaded = 0
        
        append_output_callback(f'Total file size: {total_size / 1024 / 1024:.2f} MB')
        append_output_callback('Starting download...')
        
        with open(dest_zip, 'wb') as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Update progress every 0.5 seconds
                    current_time = time.time()
                    if current_time - last_update_time >= 0.5 and total_size > 0:
                        # Calculate metrics
                        elapsed = current_time - start_time
                        downloaded_since_last = downloaded - last_downloaded
                        time_since_last = current_time - last_update_time
                        
                        # Speed in MBPS
                        speed_mbps = (downloaded_since_last / time_since_last) / (1024 * 1024)
                        
                        # Percentage
                        percentage = (downloaded / total_size) * 100
                        
                        # Time remaining
                        if speed_mbps > 0:
                            remaining_bytes = total_size - downloaded
                            remaining_seconds = remaining_bytes / (speed_mbps * 1024 * 1024)
                            remaining_time = timedelta(seconds=int(remaining_seconds))
                        else:
                            remaining_time = timedelta(seconds=0)
                        
                        # Format output
                        progress_msg = f'Download: {percentage:.1f}% | {downloaded / 1024 / 1024:.2f}/{total_size / 1024 / 1024:.2f} MB | Speed: {speed_mbps:.2f} MBPS | Time remaining: {remaining_time}'
                        append_output_callback(progress_msg)
                        
                        # Update splash screen and UI
                        splash_text = f'Downloading...\n{percentage:.1f}% Complete'
                        total_mb = total_size / (1024 * 1024) if total_size > 0 else 0
                        downloaded_mb = downloaded / (1024 * 1024)
                        stats = f"{downloaded_mb:.2f}/{total_mb:.2f} MB | {speed_mbps:.2f} MB/s"
                        update_splash_callback(label_text=splash_text, percent=percentage, stats_text=stats, speed_text=f'Download Speed: {speed_mbps:.2f} MB/s', status_text=f'{speed_mbps:.2f} MB/s | {remaining_time}')

                        # Update progress variable
                        update_progress_callback(percentage)
                        
                        last_update_time = current_time
                        last_downloaded = downloaded
        
        append_output_callback(f'Download complete: {downloaded / 1024 / 1024:.2f} MB downloaded')
        
        # Extract with progress tracking and error handling
        append_output_callback('Extracting repository...')
        extraction_success = extract_zip_with_progress(dest_zip, WORKSPACE, append_output_callback, update_splash_callback, update_progress_callback)
        
        if not extraction_success:
            append_output_callback('ERROR: ZIP extraction failed, attempting recovery...')
            # Try alternative extraction method
            try:
                append_output_callback('Attempting alternative extraction method...')
                extraction_success = extract_zip_alternative(dest_zip, WORKSPACE, append_output_callback)
            except Exception as e:
                append_output_callback(f'Alternative extraction also failed: {str(e)}')
                # Clean up and return on failure
                if dest_zip.exists():
                    dest_zip.unlink()
                return False
        
        # Find and move extracted content
        extracted_root = None
        for item in WORKSPACE.iterdir():
            if item.is_dir() and item.name.startswith('getdownload-'):
                extracted_root = item
                break
        
        if extracted_root:
            append_output_callback(f'Merging extracted folder: {extracted_root.name}')
            try:
                # Merge contents into workspace with error handling
                for child in extracted_root.iterdir():
                    target = WORKSPACE / child.name
                    try:
                        if target.exists():
                            if target.is_dir():
                                shutil.rmtree(target)
                            else:
                                target.unlink()
                        if child.is_dir():
                            append_output_callback(f'  Moving folder: {child.name}')
                            shutil.copytree(child, target)
                        else:
                            append_output_callback(f'  Moving file: {child.name}')
                            shutil.copy2(child, target)
                    except Exception as e:
                        append_output_callback(f'  WARNING: Failed to move {child.name}: {str(e)}')
                
                shutil.rmtree(extracted_root)
            except Exception as e:
                append_output_callback(f'ERROR during merge: {str(e)}')
        else:
            append_output_callback('WARNING: Could not find extracted folder, checking for direct extraction...')
        
        # Clean up zip
        if dest_zip.exists():
            try:
                dest_zip.unlink()
                append_output_callback('Cleaned up temporary ZIP file')
            except Exception as e:
                append_output_callback(f'WARNING: Could not delete ZIP file: {str(e)}')
        
        append_output_callback('Repository extraction and merge complete')
        return True
    except Exception as e:
        append_output_callback('Download/extract failed: ' + str(e))
        # Cleanup on error
        if dest_zip.exists():
            try:
                dest_zip.unlink()
            except:
                pass
        return False

def extract_zip_with_progress(zip_path, extract_path, append_output_callback, update_splash_callback, update_progress_callback):
    """Extract ZIP with comprehensive error handling, validation, and recovery."""
    try:
        # Validate inputs
        zip_path = Path(zip_path)
        extract_path = Path(extract_path)
        
        # Step 1: Pre-extraction validation
        append_output_callback('Validating ZIP file...')
        
        # Check if ZIP file exists
        if not zip_path.exists():
            append_output_callback(f'ERROR: ZIP file not found: {zip_path}')
            return False
        
        # Check if ZIP file is readable
        if not os.access(zip_path, os.R_OK):
            append_output_callback(f'ERROR: ZIP file is not readable: {zip_path}')
            return False
        
        # Check if target directory exists, create if needed
        try:
            extract_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            append_output_callback(f'ERROR: Cannot create extraction directory: {str(e)}')
            return False
        
        # Check if target directory is writable
        if not os.access(extract_path, os.W_OK):
            append_output_callback(f'ERROR: Extraction directory is not writable: {extract_path}')
            return False
        
        # Check if ZIP file is valid
        try:
            if not zipfile.is_zipfile(zip_path):
                append_output_callback('ERROR: Invalid ZIP file format')
                return False
        except Exception as e:
            append_output_callback(f'ERROR: Cannot validate ZIP file: {str(e)}')
            return False
        
        # Step 2: Check disk space
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                total_uncompressed = sum(info.file_size for info in z.infolist())
            
            stat = os.statvfs(extract_path) if hasattr(os, 'statvfs') else None
            if stat:
                available_space = stat.f_bavail * stat.f_frsize
                if available_space < total_uncompressed:
                    append_output_callback(f'WARNING: Low disk space. Available: {available_space / 1024 / 1024:.1f} MB, Need: {total_uncompressed / 1024 / 1024:.1f} MB')
        except Exception as e:
            append_output_callback(f'WARNING: Could not check disk space: {str(e)}')
        
        # Step 3: Extract with error handling
        append_output_callback('Opening ZIP file for extraction...')
        
        extracted_files = []
        skipped_files = []
        failed_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                # Test ZIP integrity
                test_result = z.testzip()
                if test_result is not None:
                    append_output_callback(f'WARNING: ZIP file may be corrupted. First bad file: {test_result}')
                
                file_list = z.namelist()
                total_files = len(file_list)
                
                if total_files == 0:
                    append_output_callback('WARNING: ZIP file is empty')
                    return True
                
                append_output_callback(f'Starting extraction of {total_files} files...')
                
                start_time = time.time()
                last_update_time = start_time
                
                for idx, file in enumerate(file_list, 1):
                    try:
                        # Skip directories
                        if file.endswith('/'):
                            extracted_files.append(file)
                            continue
                        
                        # Check for path issues (Windows max path length)
                        target_path = extract_path / file
                        full_path = str(target_path.resolve())
                        
                        if sys.platform == 'win32' and len(full_path) > 260:
                            append_output_callback(f'WARNING: Path too long (Windows limit 260), skipping: {file}')
                            skipped_files.append(file)
                            continue
                        
                        # Create parent directory if needed
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Extract file with retry logic
                        max_retries = 2
                        for attempt in range(max_retries):
                            try:
                                z.extract(file, extract_path)
                                extracted_files.append(file)
                                break
                            except PermissionError as pe:
                                if attempt < max_retries - 1:
                                    append_output_callback(f'RETRY {attempt + 1}: Permission issue with {file}, retrying...')
                                    time.sleep(0.5)
                                else:
                                    raise
                            except Exception as fe:
                                if attempt < max_retries - 1:
                                    append_output_callback(f'RETRY {attempt + 1}: Extract issue with {file}, retrying...')
                                    time.sleep(0.5)
                                else:
                                    raise
                    
                    except PermissionError as pe:
                        append_output_callback(f'WARNING: Permission denied extracting {file}')
                        failed_files.append((file, str(pe)))
                    except UnicodeDecodeError as ue:
                        append_output_callback(f'WARNING: Filename encoding issue with {file}')
                        skipped_files.append(file)
                    except Exception as fe:
                        append_output_callback(f'WARNING: Failed to extract {file}: {str(fe)}')
                        failed_files.append((file, str(fe)))
                    
                    # Update progress every 0.5 seconds
                    current_time = time.time()
                    if current_time - last_update_time >= 0.5:
                        elapsed = current_time - start_time
                        percentage = (idx / total_files) * 100
                        
                        # Speed in files per second
                        speed_fps = idx / elapsed if elapsed > 0 else 0
                        
                        # Time remaining
                        if speed_fps > 0:
                            remaining_files = total_files - idx
                            remaining_seconds = remaining_files / speed_fps
                            remaining_time = timedelta(seconds=int(remaining_seconds))
                        else:
                            remaining_time = timedelta(seconds=0)
                        
                        progress_msg = f'Extract: {percentage:.1f}% | {idx}/{total_files} files | Speed: {speed_fps:.1f} files/sec | Time remaining: {remaining_time}'
                        append_output_callback(progress_msg)
                        
                        # Update splash screen and UI
                        splash_text = f'Extracting...\n{percentage:.1f}% Complete'
                        stats = f"{idx}/{total_files} files | {speed_fps:.1f} files/sec"
                        update_splash_callback(label_text=splash_text, percent=percentage, stats_text=stats, speed_text=f'Extract Speed: {speed_fps:.1f} files/sec', status_text=f'{speed_fps:.1f} files/sec | {remaining_time}')
                        # Update progress variable
                        update_progress_callback(percentage)
                        last_update_time = current_time
        
        except zipfile.BadZipFile as bz:
            append_output_callback(f'ERROR: ZIP file is corrupted or invalid: {str(bz)}')
            return False
        except Exception as e:
            append_output_callback(f'ERROR: Unexpected extraction error: {str(e)}')
            return False
        
        # Step 4: Report results
        append_output_callback(f'Extraction complete:')
        append_output_callback(f'  ✓ Successfully extracted: {len(extracted_files)} items')
        if skipped_files:
            append_output_callback(f'  ⊘ Skipped: {len(skipped_files)} items')
        if failed_files:
            append_output_callback(f'  ✗ Failed: {len(failed_files)} items')
            for file, reason in failed_files[:5]:  # Show first 5 failures
                append_output_callback(f'    - {file}: {reason}')
            if len(failed_files) > 5:
                append_output_callback(f'    ... and {len(failed_files) - 5} more failures')
        
        # Consider success if at least 90% of files extracted
        success_rate = len(extracted_files) / total_files if total_files > 0 else 0
        if success_rate >= 0.9:
            append_output_callback(f'SUCCESS: Extraction successful with {success_rate*100:.1f}% success rate')
            return True
        elif success_rate >= 0.5:
            append_output_callback(f'PARTIAL: Extraction partially successful with {success_rate*100:.1f}% success rate')
            return True
        else:
            append_output_callback(f'FAILED: Extraction success rate too low ({success_rate*100:.1f}%)')
            return False
            
    except Exception as e:
        append_output_callback(f'FATAL: Extraction error: {str(e)}')
        return False

def extract_zip_alternative(zip_path, extract_path, append_output_callback):
    """Alternative extraction method using Python's zipfile with different strategy."""
    try:
        zip_path = Path(zip_path)
        extract_path = Path(extract_path)
        
        append_output_callback('Using alternative extraction method...')
        
        extract_path.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as z:
            file_list = z.namelist()
            total_files = len(file_list)
            
            extracted = 0
            failed = []
            
            for idx, file in enumerate(file_list, 1):
                try:
                    # Read and write manually instead of using extract
                    if file.endswith('/'):
                        target = extract_path / file
                        target.mkdir(parents=True, exist_ok=True)
                        extracted += 1
                    else:
                        target = extract_path / file
                        target.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Write file content
                        with z.open(file) as source:
                            with open(target, 'wb') as dest:
                                content = source.read()
                                dest.write(content)
                        extracted += 1
                except Exception as e:
                    failed.append((file, str(e)))
            
            append_output_callback(f'Alternative extraction: {extracted}/{total_files} files extracted')
            if failed:
                append_output_callback(f'Alternative extraction: {len(failed)} files failed')
            return extracted / total_files >= 0.9
    except Exception as e:
        append_output_callback(f'Alternative extraction failed: {str(e)}')
        return False
