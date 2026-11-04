#!/bin/sh
# Run the test suite. No network or packages needed.
cd "$(dirname "$0")/.." || exit 1
exec "${PYTHON:-python3}" -m unittest discover -s tests -v
