#!/bin/sh
# Remaining census runs in order (see PROTOCOL.md); resumable.
set -e
cd "$(dirname "$0")"
python3 census.py reps --a2 0 --workers 3 > ../outputs/reps-a0.log 2>&1
python3 census.py reps --a2 1 --workers 3 > ../outputs/reps-a1.log 2>&1
python3 census.py floor --a2 1 --workers 3 > ../outputs/floor-a1.log 2>&1
echo done
