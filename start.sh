#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! python3 -c 'import PyQt5, zmq, cryptography, numpy, yaml; from gnuradio import gr, iio' >/dev/null 2>&1; then
    echo 'Install the required packages once, then run bash start.sh again:'
    echo 'sudo apt install gnuradio python3-pyqt5 python3-zmq python3-cryptography python3-numpy python3-yaml python3-pil ffmpeg g++ libiio-utils'
    exit 1
fi
if [ ! -f sdrchat/native/libnlms.so ] || [ ! -f flowgraphs/generated/csma_transceiver.py ]; then
    echo 'Preparing the radio for this computer...'
    g++ -O3 -std=c++17 -shared -fPIC sdrchat/native/nlms.cpp -o sdrchat/native/libnlms.so
    python3 tools/embed_flowgraph.py
    mkdir -p flowgraphs/generated
    grcc -o flowgraphs/generated flowgraphs/Working1.0_csma.grc
fi
if [ "${1:-}" = "--prepare-only" ]; then
    exit 0
fi
if [ "$#" -gt 0 ]; then
    exec python3 -m sdrchat.app --config "$1"
elif [ -f .coordinator ]; then
    exec python3 -m sdrchat.app --config configs/node_a.json
else
    exec python3 -m sdrchat.app
fi
