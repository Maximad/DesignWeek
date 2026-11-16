"""Generate a PBKDF2 password verifier to store ONLY in the VPS .env file.
Usage: python -m server.hash_password (prompts locally, never commits plaintext).
"""
import getpass
import hashlib
import secrets
password = getpass.getpass("New admin password: ")
if len(password) < 14:
    raise SystemExit("Choose a password of at least 14 characters")
confirmation = getpass.getpass("Repeat password: ")
if password != confirmation:
    raise SystemExit("Passwords do not match")
salt = secrets.token_bytes(16)
iterations = 600000
value = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations).hex()
print(f"DW_ADMIN_PASSWORD_HASH=pbkdf2_sha256${iterations}${salt.hex()}${value}")