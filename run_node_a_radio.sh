#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m sdrchat.hardware --config configs/node_a.json
