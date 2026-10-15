#!/bin/sh
set -eu
runtime=/Volumes/SSD990-2/cryptanalysis/ecc2k130/runner/research/production/2026-10-15-modal-restart-runtime
cd /Volumes/SSD990-2/crypto/ecc2k130
export PYTHONPATH="$runtime/pylibs"
export TMPDIR="$runtime/tmp"
exec /Users/adamburan/.pyenv/versions/3.12.8/bin/python3 modal_sync.py \
  --curve 131 --run-ids 8009,8010 --bucket ecc2k130-590183823895 \
  --state-dir "$runtime/modal-sync-state" --watch 30 \
  >> "$runtime/modal-sync.log" 2>&1
