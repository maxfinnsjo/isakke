#!/usr/bin/env bash
# Deploy the slim ISAKKE demo to the shared VPS (same box and key as jobhunt: ~/.ssh/jobhunt_deploy via ~/.ssh/config).
#
#   deploy/deploy.sh             build + start (or update)
#   deploy/deploy.sh --dry-run   show what would be sent, change nothing
#   deploy/deploy.sh --stop      take it down at once (frees ~1.3 GB if it was in use)
#   deploy/deploy.sh --force     skip the free-memory check
#
# Nothing sensitive is shipped: the repo holds public law texts and SCB lookups, no secrets. No sudo, no open ports.
set -euo pipefail

VPS="kl3p0@206.168.215.98"
DIR="apps/isakke"
URL="https://isakke.206.168.215.98.sslip.io/"
MIN_FREE_MB=1800  # the stack can use up to ~1.5 GB; below this the box is already busy

cd "$(dirname "$0")/.."
DRY="" FORCE=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY="--dry-run" ;;
    --force)   FORCE=1 ;;
    --stop)    ssh "$VPS" "cd ~/$DIR && docker compose down" && echo "stopped"; exit ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ -n "$(git status --porcelain)" ]; then echo "ABORTED: commit first, the VPS should run a known version." >&2; exit 1; fi

free=$(ssh "$VPS" "free -m | awk '/^Mem:/ {print \$7}'")
echo "VPS available memory: ${free} MB (need ${MIN_FREE_MB})"
if [ "$free" -lt "$MIN_FREE_MB" ] && [ -z "$FORCE" ]; then echo "ABORTED: not enough free memory (use --force to override)." >&2; exit 1; fi

echo "Syncing $(git rev-parse --short HEAD) to $VPS:~/$DIR/"
[ -n "$DRY" ] || ssh "$VPS" "mkdir -p ~/$DIR"
rsync -az --delete $DRY --info=stats1 -e ssh ./isakke.py ./index.html ./index.npz ./laws ./Dockerfile "$VPS:~/$DIR/"
[ -n "$DRY" ] && exit 0
scp -q deploy/docker-compose.yml "$VPS:~/$DIR/docker-compose.yml"

echo "Building and starting (first run pulls ~7 GB of images and the model)"
ssh "$VPS" "cd ~/$DIR && docker compose up -d --build && docker compose ps"

echo "Waiting for Caddy and the certificate…"
for i in $(seq 1 30); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$URL" || true)" = 200 ] && { echo "up: $URL"; exit 0; }
  sleep 5
done
echo "not answering yet; check: ssh $VPS 'cd ~/$DIR && docker compose logs --tail 50'" >&2; exit 1
