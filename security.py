import os
import subprocess
import base64
import json
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

CONFIG_FILE = "config.tge"

import winreg

def get_device_id():
    """Retrieves the Windows Machine GUID from the Registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return value
    except Exception as e:
        print(f"Error getting device ID from registry: {e}")
        # Fallback to uuid node if registry fails (unlikely on Windows)
        import uuid
        return str(uuid.getnode())

def _derive_key(device_id):
    """Derives a safe url-safe base64 key from the device ID."""
    # Salt should be constant for the same device to reproduce the key, 
    # but ideally random per file. Here we bind it to the device ID itself 
    # effectively making the device ID the "password"
    salt = b'static_salt_tg_exporter' 
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(device_id.encode()))
    return key

def save_encrypted_config(api_id, api_hash, phone):
    """Saves the login credentials to an encrypted file bound to this device."""
    try:
        device_id = get_device_id()
        key = _derive_key(device_id)
        f = Fernet(key)
        
        data = json.dumps({
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone
        }).encode()
        
        encrypted_data = f.encrypt(data)
        
        with open(CONFIG_FILE, "wb") as file:
            file.write(encrypted_data)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def load_encrypted_config():
    """Loads and decrypts credentials if the file exists and matches the device."""
    if not os.path.exists(CONFIG_FILE):
        return None
        
    try:
        device_id = get_device_id()
        key = _derive_key(device_id)
        f = Fernet(key)
        
        with open(CONFIG_FILE, "rb") as file:
            encrypted_data = file.read()
            
        decrypted_data = f.decrypt(encrypted_data)
        return json.loads(decrypted_data)
    except Exception as e:
        # Only print error if file existed but couldn't be read (e.g. wrong device)
        print(f"Warning: Could not decrypt config (Resetting): {e}")
        return None
