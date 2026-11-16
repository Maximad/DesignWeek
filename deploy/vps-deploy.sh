#!/usr/bin/env bash
set -euo pipefail
# Run as a VPS user with Docker Compose access. Does NOT touch other websites/services.
DEST="${DESIGNWEEK_DEST:-$HOME/apps/designweek}"
mkdir -p "$(dirname "$DEST")"
if [ ! -d "$DEST/.git" ]; then
  git clone --branch main --depth 1 https://github.com/Maximad/DesignWeek.git "$DEST"
fi
cd "$DEST"
git pull --ff-only origin main
if [ ! -f .env ]; then
  echo 'Missing private .env; refusing to deploy without credentials.' >&2
  exit 1
fi
if grep -q 'REPLACE_WITH' .env; then
  echo 'Placeholder credentials found; refusing to deploy.' >&2
  exit 1
fi
docker compose -f compose.yml up -d --build
docker compose -f compose.yml ps
curl --fail --silent --show-error http://127.0.0.1:8926/healthz