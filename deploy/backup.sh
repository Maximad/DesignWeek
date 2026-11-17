#!/usr/bin/env bash
set -euo pipefail
# Live SQLite backup + private attachments; only reads the running DesignWeek app.
# Does not restart the container, touch Caddy, or expose data publicly.
cd "${DESIGNWEEK_DEST:-$HOME/apps/designweek}"
umask 077
mkdir -p backups
chmod 700 backups
NOW="$(date -u +%Y%m%dT%H%M%SZ)"
CID="$(docker compose -f compose.yml ps -q designweek)"
test -n "$CID" || { echo 'DesignWeek container not running' >&2; exit 1; }

# Docker cp can fail when its source is on the container's /tmp tmpfs.
# Create the SQLite-consistent snapshot inside the private persistent /data volume,
# stream it directly from the running container, and remove the snapshot on exit.
SNAPSHOT="/data/.designweek-backup-${NOW}-$$.sqlite3"
DB_PART="backups/.applications-${NOW}-$$.partial"
FILES_PART="backups/.uploads-${NOW}-$$.partial"
DB_OUT="backups/applications-${NOW}.sqlite3"
FILES_OUT="backups/uploads-${NOW}.tar.gz"
cleanup() {
  docker exec "$CID" python -c 'import pathlib,sys; pathlib.Path(sys.argv[1]).unlink(missing_ok=True)' "$SNAPSHOT" >/dev/null 2>&1 || true
  rm -f "$DB_PART" "$FILES_PART"
}
trap cleanup EXIT
if [[ -e "$DB_OUT" || -e "$FILES_OUT" ]]; then
  echo 'Backup target already exists; retry after the next UTC second.' >&2
  exit 1
fi

docker exec "$CID" python -c '
import sqlite3,sys
source = sqlite3.connect("file:/data/applications.sqlite3?mode=ro", uri=True)
target = sqlite3.connect(sys.argv[1])
try:
    source.backup(target)
finally:
    target.close()
    source.close()
' "$SNAPSHOT"
docker exec "$CID" cat "$SNAPSHOT" > "$DB_PART"

# Validate the snapshot before reporting success.
python3 - "$DB_PART" <<'PY'
import sqlite3,sys
conn = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
try:
    status = conn.execute("PRAGMA quick_check").fetchone()[0]
    assert status == "ok", f"Database integrity check failed: {status}"
    conn.execute("SELECT COUNT(*) FROM applications").fetchone()
finally:
    conn.close()
PY

# Export private attachments to a compressed archive without exposing the volume.
docker exec "$CID" python -c '
import sys,tarfile
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    archive.add("/data/private-uploads", arcname="private-uploads")
' > "$FILES_PART"
python3 - "$FILES_PART" <<'PY'
import sys,tarfile
with tarfile.open(sys.argv[1], "r:gz") as archive:
    assert any(item.name == "private-uploads" for item in archive), "Attachment archive missing root directory"
PY

mv "$DB_PART" "$DB_OUT"
mv "$FILES_PART" "$FILES_OUT"
chmod 600 "$DB_OUT" "$FILES_OUT"
echo "Backup verified: $(pwd)/$DB_OUT and $(pwd)/$FILES_OUT"
echo 'Keep backups private and transfer encrypted copies off the VPS.'
