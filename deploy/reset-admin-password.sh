#!/usr/bin/env bash
set -euo pipefail
# Reset only DesignWeek's private administrator password.
# Never print, log or commit the password. Existing users/data remain intact.
cd "${DESIGNWEEK_DEST:-$HOME/apps/designweek}"
test -f .env || { echo 'Missing private .env file.' >&2; exit 1; }
python3 - <<'PY'
from pathlib import Path
import getpass
import hashlib
import os
import secrets
import tempfile

path = Path(".env")
original = path.read_text(encoding="utf-8")
assert "DW_ADMIN_PASSWORD_HASH=" in original, "Missing DW_ADMIN_PASSWORD_HASH in .env"
username = next((line.split("=", 1)[1].strip()
    for line in original.splitlines() if line.startswith("DW_ADMIN_USERNAME=")), "admin")

print("DesignWeek admin username:", username)
first = getpass.getpass("New admin password (14+ characters): ")
second = getpass.getpass("Confirm new password: ")
if len(first) < 14 or first != second:
    raise SystemExit("Password mismatch or fewer than 14 characters; no changes made.")

salt = secrets.token_bytes(16)
hashed = hashlib.pbkdf2_hmac("sha256", first.encode(), salt, 600000).hex()
value = f"pbkdf2_sha256:600000:{salt.hex()}:{hashed}"
lines = original.splitlines()
matches = [i for i, line in enumerate(lines) if line.startswith("DW_ADMIN_PASSWORD_HASH=")]
if len(matches) != 1:
    raise SystemExit("Expected exactly one DW_ADMIN_PASSWORD_HASH entry; no changes made.")
lines[matches[0]] = "DW_ADMIN_PASSWORD_HASH=" + value

# Atomic mode-0600 write keeps the private .env safe even if interrupted.
fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".env-admin-", text=True)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
print("New password hash saved. Password not displayed.")
PY
echo "Restarting DesignWeek only to activate the new password..."
if [[ -f compose.gateway.yml ]]; then
  docker compose -f compose.yml -f compose.gateway.yml up -d --no-deps --force-recreate designweek
else
  docker compose -f compose.yml up -d --no-deps --force-recreate designweek
fi
echo "Admin password changed. Wait for the DesignWeek container to become healthy."
