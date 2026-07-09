import os
import json
import requests
from cryptography.fernet import Fernet
from datetime import datetime, timezone, timedelta
from models.config.settings import LOGIN_API_URL, SECRET_KEY, AUTH_FILE

def check_offline_login_status():
    """
    Check if the user has a valid cached login session without loading CustomTkinter.
    Returns:
        tuple: (login_successful: bool, user_data: dict or None, error_message: str or None)
    """
    if not os.path.exists(AUTH_FILE):
        return False, None, None

    try:
        with open(AUTH_FILE, 'r') as f:
            encrypted_response = f.read().strip()
        
        cipher = Fernet(SECRET_KEY)
        decrypted_bytes = cipher.decrypt(encrypted_response.encode('utf-8'))
        decrypted_json = json.loads(decrypted_bytes.decode('utf-8'))
        
        if decrypted_json.get("success"):
            # 1. Local Expiration Check
            ist = timezone(timedelta(hours=5, minutes=30))
            current_time_ist = datetime.now(ist)
            expire_date_str = decrypted_json.get('expire_date')
            is_expired_locally = False
            
            if expire_date_str:
                try:
                    if len(expire_date_str) > 10:
                        expire_dt = datetime.strptime(expire_date_str, "%Y-%m-%d %H:%M:%S")
                    else:
                        expire_dt = datetime.strptime(expire_date_str, "%Y-%m-%d")
                    expire_dt = expire_dt.replace(tzinfo=ist)
                    if current_time_ist > expire_dt:
                        is_expired_locally = True
                except Exception:
                    pass

            # 2. Network Sync Check
            username = decrypted_json.get("username")
            password = decrypted_json.get("password")
            
            if username and password:
                try:
                    data = {"username": username, "password": password}
                    # Fast network timeout (3s) to prevent startup lag
                    response = requests.post(LOGIN_API_URL, json=data, timeout=3)
                    if response.status_code == 200:
                        new_encrypted_response = response.json().get('data')
                        if new_encrypted_response:
                            # Overwrite local file with fresh data
                            os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
                            with open(AUTH_FILE, 'w') as f:
                                f.write(new_encrypted_response)
                                
                            new_decrypted_bytes = cipher.decrypt(new_encrypted_response.encode('utf-8'))
                            new_decrypted_json = json.loads(new_decrypted_bytes.decode('utf-8'))
                            
                            if new_decrypted_json.get("success") and new_decrypted_json.get("is_active_subscription"):
                                return True, new_decrypted_json, None
                            else:
                                return False, None, "Subscription is expired or inactive on the server."
                except requests.exceptions.RequestException:
                    pass # Offline, fallback to local checks
                    
            # 3. Handle Offline Fallback
            if is_expired_locally:
                return False, None, "Plan expired locally. Connect to internet to verify renewal."
            else:
                if decrypted_json.get("is_active_subscription"):
                    return True, decrypted_json, None
                else:
                    return False, None, "Subscription is inactive."
    except Exception:
        # Corrupted file/session, remove file to allow clean relogin
        try:
            os.remove(AUTH_FILE)
        except Exception:
            pass

    return False, None, None
