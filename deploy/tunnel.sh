#!/usr/bin/env bash
# No-signup SSH tunnel (localhost.run) exposing the local contxt app at a public URL.
# The URL changes every time this restarts - it's logged here and in the systemd journal
# (`journalctl -u contxt-tunnel -f`). Swap this for cloudflared later if it proves too flaky.
set -euo pipefail

LOG_DIR="/home/dahrs/contxt/logs"
mkdir -p "$LOG_DIR"

ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:localhost:8000 nokey@localhost.run \
  | tee -a "$LOG_DIR/tunnel.log"
