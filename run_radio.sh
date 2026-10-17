#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f "${1:-configs/my_node.json}" ]; then
    echo 'Profile not found. Create the coordinator profile, or run bash run_node_b.sh to import your personal invitation.' >&2
    exit 1
fi
exec python3 -m sdrchat.hardware --config "${1:-configs/my_node.json}"
