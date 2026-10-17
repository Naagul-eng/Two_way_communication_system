#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f "${1:-configs/my_node.json}" ]; then
    echo 'Open Pixel Pulse with bash run_app.sh and import your personal invitation first.'
    exit 1
fi
exec python3 -m sdrchat.hardware --config "${1:-configs/my_node.json}"
