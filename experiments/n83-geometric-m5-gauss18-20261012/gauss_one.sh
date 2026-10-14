#!/bin/sh
# Admit only the smallest recovered XOR component for a bounded comparison.
exec /opt/homebrew/bin/cryptominisat5 --maxmatrixrows 4096 --maxmatrixcols 4096 --maxnummatrices 1 "$@"
