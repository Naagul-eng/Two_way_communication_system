#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f configs/node_a.json ]; then
    echo 'Create the coordinator profile first: python3 tools/create_coordinator.py --name "User 1"' >&2
    exit 1
fi
exec bash run_app.sh --config configs/node_a.json "$@"
