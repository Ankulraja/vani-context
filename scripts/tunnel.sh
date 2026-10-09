#!/usr/bin/env bash
# Public URL for the VANI Context API so Sarvam's tools can reach it.
#
#   ngrok with a free static domain (URL never changes, no tool re-pointing):
#     1. sign up at https://dashboard.ngrok.com (free), copy the authtoken
#     2. ngrok config add-authtoken <token>
#     3. claim a free static domain: dashboard → Domains → "+ New Domain" (e.g. vani-context.ngrok-free.app)
#     4. put NGROK_DOMAIN=<that domain> in .env, then run:  scripts/tunnel.sh
#   Without NGROK_DOMAIN this falls back to a cloudflared quick tunnel (URL changes every restart).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && export $(grep -E '^NGROK_DOMAIN=' .env | xargs) || true

if [ -n "${NGROK_DOMAIN:-}" ] && command -v ngrok >/dev/null; then
  echo "https://$NGROK_DOMAIN" > /tmp/vani_public_url.txt
  echo "public URL: https://$NGROK_DOMAIN   (static — agent tools keep working after restarts)"
  exec ngrok http --url="$NGROK_DOMAIN" 8000 --log=stdout > /tmp/ngrok.log
else
  echo "NGROK_DOMAIN not set (or ngrok missing) → cloudflared quick tunnel; the URL changes on every restart."
  cloudflared tunnel --url http://localhost:8000 > /tmp/cloudflared.log 2>&1 &
  for i in $(seq 1 30); do
    url=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/cloudflared.log | head -1 || true)
    [ -n "$url" ] && break; sleep 1
  done
  echo "$url" > /tmp/vani_public_url.txt
  echo "public URL: $url   (re-point both agent tools + commit after every restart)"
  wait
fi
