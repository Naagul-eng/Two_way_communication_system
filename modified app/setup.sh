#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
g++ -O3 -std=c++17 -shared -fPIC sdrchat/native/nlms.cpp -o sdrchat/native/libnlms.so
if [ -f ../Working1.0.grc ]; then
    python3 tools/build_flowgraph.py
fi
python3 tools/embed_flowgraph.py
mkdir -p flowgraphs/generated
grcc -o flowgraphs/generated flowgraphs/Working1.0_csma.grc
python3 -m unittest discover -s tests -v
