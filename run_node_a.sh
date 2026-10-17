#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec bash run_node_a_chat.sh "$@"
