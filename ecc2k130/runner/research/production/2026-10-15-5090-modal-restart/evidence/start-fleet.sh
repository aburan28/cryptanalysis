#!/bin/sh
set -eu
runtime=/Volumes/SSD990-2/cryptanalysis/ecc2k130/runner/research/production/2026-10-15-modal-restart-runtime
cd /Volumes/SSD990-2/crypto/ecc2k130
export TMPDIR="$runtime/tmp"
export ECC_MODAL_CAMPAIGN_STATE="$runtime/modal-calls.json"
export MODAL_SYNC_SESSION=ecc2k130-modal-sync
export CURVE=131 RUNID=8009 COUNT=2 HOURS=4 PASSES=0 DEPLOY=0
exec ./run.sh fleet >> "$runtime/modal-fleet.log" 2>&1
