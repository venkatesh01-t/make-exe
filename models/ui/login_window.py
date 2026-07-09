import json
import requests
import customtkinter as ctk
from cryptography.fernet import Fernet
import os
from models.config.settings import LOGIN_API_URL, SECRET_KEY, AUTH_FILE
from models.design_system.tokens import Colors
from models.design_system.fonts import make_font, Fonts
from models.ui.components import PrimaryButton

class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Clinic Manager - Login")
        self.geometry("400x500")
        self.resizable(False, False)
        
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=Colors.pair(Colors.BG, Colors.DARK_BG))
        
        self.login_successful = False
        self.user_data = None
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        if self._check_offline_login():
            return
            
        self._setup_ui()

    def _check_offline_login(self):
        if os.path.exists(AUTH_FILE):
            try:
                with open(AUTH_FILE, 'r') as f:
                    encrypted_response = f.read().strip()
                
                cipher = Fernet(SECRET_KEY)
                decrypted_bytes = cipher.decrypt(encrypted_response.encode('utf-8'))
                decrypted_json = json.loads(decrypted_bytes.decode('utf-8'))
                
                if decrypted_json.get("success") and decrypted_json.get("is_active_subscription"):
                    self.login_successful = True
                    self.user_data = decrypted_json
                    self.after(0, self.destroy) # close UI correctly
                    return True
            except Exception as e:
                # Corrupted or invalid key, remove file and fallback to login
                try:
                    os.remove(AUTH_FILE)
                except:
                    pass
        return False

    def _setup_ui(self):
        # Container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=40, pady=40)
        
        # Title
        ctk.CTkLabel(
            self.container, 
            text="Welcome Back", 
            font=make_font(Fonts.XL, "bold"),
            text_color=Colors.PRIMARY
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            self.container,
            text="Please login to your account",
            font=make_font(Fonts.MD),
            text_color=Colors.TEXT_SECONDARY
        ).pack(pady=(0, 30))
        
        # Username
        self.username_entry = ctk.CTkEntry(
            self.container, 
            placeholder_text="Username",
            height=45,
            font=make_font(Fonts.MD)
        )
        self.username_entry.pack(fill="x", pady=10)
        
        # Password
        self.password_entry = ctk.CTkEntry(
            self.container, 
            placeholder_text="Password",
            show="*",
            height=45,
            font=make_font(Fonts.MD)
        )
        self.password_entry.pack(fill="x", pady=10)
        
        # Error Label
        self.error_label = ctk.CTkLabel(
            self.container,
            text="",
            text_color=Colors.DANGER,
            font=make_font(Fonts.SM)
        )
        self.error_label.pack(pady=5)
        
        # Login Button
        self.login_btn = PrimaryButton(
            self.container, 
            text="Login", 
            command=self.perform_login
        )
        self.login_btn.pack(fill="x", pady=20)
        
    def perform_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            self.show_error("Please enter both username and password")
            return
            
        self.login_btn.configure(state="disabled", text="Logging in...")
        self.error_label.configure(text="")
        
        # Call API
        try:
            cipher = Fernet(SECRET_KEY)
            data = {
                "username": username,
                "password": password
            }
            response = requests.post(LOGIN_API_URL, json=data, timeout=10)
            
            if response.status_code == 200:
                encrypted_response = response.json().get('data')
                
                if not encrypted_response:
                    self.show_error("Invalid response from server")
                    return
                
                # Decrypt
                decrypted_bytes = cipher.decrypt(encrypted_response.encode('utf-8'))
                decrypted_json = json.loads(decrypted_bytes.decode('utf-8'))
                
                if decrypted_json.get("success"):
                    if decrypted_json.get("is_active_subscription"):
                        self.login_successful = True
                        self.user_data = decrypted_json
                        
                        # Save encrypted response to file
                        os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
                        with open(AUTH_FILE, 'w') as f:
                            f.write(encrypted_response)
                            
                        self.destroy()
                    else:
                        self.show_error("Subscription is inactive or expired")
                else:
                    self.show_error(decrypted_json.get("error", "Invalid credentials"))
            else:
                self.show_error(f"Server error: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            self.show_error("Network error: Could not connect to server")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")
        finally:
            self.login_btn.configure(state="normal", text="Login")

    def show_error(self, message):
        self.error_label.configure(text=message)

    def on_closing(self):
        self.login_successful = False
        self.destroy()
