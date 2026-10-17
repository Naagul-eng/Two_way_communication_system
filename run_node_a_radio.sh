#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec bash run_radio.sh configs/node_a.json
