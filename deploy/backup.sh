#!/usr/bin/env bash
set -euo pipefail
cd "${DESIGNWEEK_DEST:-$HOME/apps/designweek}"
mkdir -p backups && chmod 700 backups
NOW="$(date -u +%Y%m%dT%H%M%SZ)"
CID="$(docker compose -f compose.yml ps -q designweek)"
test -n "$CID" || { echo 'DesignWeek container not running' >&2; exit 1; }
docker exec "$CID" python -c "import sqlite3; src=sqlite3.connect('/data/applications.sqlite3'); out=sqlite3.connect('/tmp/designweek-backup.sqlite3'); src.backup(out); out.close(); src.close()"
docker cp "$CID:/tmp/designweek-backup.sqlite3" "backups/applications-$NOW.sqlite3"
# File attachments remain in the container's private named volume.
# Export the directory without extracting or exposing its contents publicly.
docker cp "$CID:/data/private-uploads" "backups/uploads-$NOW"
chmod -R go-rwx "backups/applications-$NOW.sqlite3" "backups/uploads-$NOW"
echo "Backup stored at $(pwd)/backups (transfer encrypted offsite)"