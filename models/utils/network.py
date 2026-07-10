import socket
import time
import threading

def find_local_ip(logger_callback=None):
    """Find local IP address with multiple fallback methods."""
    # Method 1: Try connecting to external DNS (Google)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip != '127.0.0.1':
            return ip
    except Exception as e:
        if logger_callback:
            logger_callback(f'Method 1 (Google DNS) failed: {str(e)}')
    
    # Method 2: Try connecting to Cloudflare DNS
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(('1.1.1.1', 53))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip != '127.0.0.1':
            return ip
    except Exception as e:
        if logger_callback:
            logger_callback(f'Method 2 (Cloudflare DNS) failed: {str(e)}')
    
    # Method 3: Try localhost (fallback)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(('localhost', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip != '127.0.0.1':
            return ip
    except Exception:
        pass
    
    # Method 4: Use hostname resolution
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and ip != '127.0.0.1':
            if logger_callback:
                logger_callback(f'Using hostname resolution: {ip}')
            return ip
    except Exception:
        pass
    
    # Final fallback
    if logger_callback:
        logger_callback('WARNING: Could not detect local IP, using localhost')
    return '127.0.0.1'

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except OSError:
            return True

def network_monitor(app_state, logger_callback, url_updater_callback):
    """
    Monitor for network/IP address changes.
    
    app_state: object/dict with 'network_monitor_running', 'server_running', 'last_ip_check_time', 'current_ip', 'server_port'
    """
    app_state['network_monitor_running'] = True
    consecutive_errors = 0
    
    while app_state.get('network_monitor_running') and app_state.get('server_running'):
        try:
            # Check for IP change every 5 seconds (rate limiting)
            current_time = time.time()
            if current_time - app_state.get('last_ip_check_time', 0) < 5:
                time.sleep(0.5)
                continue
            
            app_state['last_ip_check_time'] = current_time
            
            # Get current IP
            new_ip = find_local_ip(logger_callback)
            
            # Check if IP has changed
            if app_state.get('current_ip') is not None and new_ip != app_state.get('current_ip'):
                logger_callback(f'⚠️ NETWORK CHANGE DETECTED: IP changed from {app_state.get("current_ip")} to {new_ip}')
                url_updater_callback(new_ip)
                consecutive_errors = 0
            
            app_state['current_ip'] = new_ip
            consecutive_errors = 0
            
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors <= 3:  # Log first 3 errors only
                logger_callback(f'Network monitor error: {str(e)}')
            
            if consecutive_errors > 10:
                logger_callback('Network monitor: Too many errors, stopping monitoring')
                app_state['network_monitor_running'] = False
            
            time.sleep(1)
