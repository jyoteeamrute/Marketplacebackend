import base64

from cryptography.fernet import Fernet
from django.conf import settings

# Generate a secret key (Run once and store it in settings)
# key = Fernet.generate_key()
# Store the key in settings.py
# SECRET_ENCRYPTION_KEY = key.decode()

# Encryption and Decryption Functions
def get_cipher():
    key = settings.SECRET_ENCRYPTION_KEY.encode()
    return Fernet(key)

def encrypt_data(data):
    cipher = get_cipher()
    return cipher.encrypt(data.encode()).decode()

def decrypt_data(data):
    cipher = get_cipher()
    return cipher.decrypt(data.encode()).decode()