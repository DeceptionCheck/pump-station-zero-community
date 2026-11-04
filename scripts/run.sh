#!/bin/sh
# Start the local practice station on 127.0.0.1 (default port 8180). Stop with Ctrl+C.
cd "$(dirname "$0")/.." || exit 1
exec "${PYTHON:-python3}" -m community.server --port "${1:-8180}"
