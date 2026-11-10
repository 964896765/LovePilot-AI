"""Local key protection and password-encrypted, authenticated backups."""
import base64
import ctypes
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


def _dpapi(data, protect):
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    operation = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        ctypes.windll.kernel32.LocalFree(output.data)


class Vault:
    def __init__(self, path):
        configured = os.getenv("LOVEPILOT_DATA_KEY")
        if configured:
            key = configured.encode()
        else:
            key_path = Path(path)
            key_path.parent.mkdir(parents=True, exist_ok=True)
            if not key_path.exists():
                key = Fernet.generate_key()
                wrapped = _dpapi(key, True) if os.name == "nt" else key
                try:
                    descriptor = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    with os.fdopen(descriptor, "wb") as stream:
                        stream.write(wrapped)
                except FileExistsError:
                    pass
            wrapped = key_path.read_bytes()
            key = _dpapi(wrapped, False) if os.name == "nt" else wrapped
        self.fernet = Fernet(key)

    def seal(self, value):
        return "lp1:" + self.fernet.encrypt(value.encode()).decode()

    def open(self, value):
        if not value.startswith("lp1:"):
            raise ValueError("unencrypted storage value")
        return self.fernet.decrypt(value[4:].encode()).decode()


def encrypt_backup(document, password):
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("backup password requires at least 12 characters")
    salt, nonce = os.urandom(16), os.urandom(12)
    key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps(document, ensure_ascii=False).encode(), b"LovePilot backup v1")
    return {"format": "lovepilot-backup-v1", "payload": base64.b64encode(salt + nonce + ciphertext).decode()}


def decrypt_backup(envelope, password):
    if envelope.get("format") != "lovepilot-backup-v1" or not isinstance(password, str) or len(password) < 12:
        raise ValueError("invalid backup format or password")
    blob = base64.b64decode(envelope["payload"], validate=True)
    if len(blob) < 44:
        raise ValueError("invalid backup payload")
    key = Scrypt(salt=blob[:16], length=32, n=2**15, r=8, p=1).derive(password.encode())
    return json.loads(AESGCM(key).decrypt(blob[16:28], blob[28:], b"LovePilot backup v1"))
