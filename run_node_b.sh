#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec bash run_node_b_chat.sh "$@"
