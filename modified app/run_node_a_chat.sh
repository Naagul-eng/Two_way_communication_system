#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec bash start.sh configs/node_a.json
