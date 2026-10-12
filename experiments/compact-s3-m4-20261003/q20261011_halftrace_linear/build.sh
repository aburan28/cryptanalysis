#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CADICAL_PREFIX=${CADICAL_PREFIX:-/opt/homebrew/opt/cadical}
PYTHON_CONFIG=${PYTHON_CONFIG:-/opt/homebrew/bin/python3-config}
OUT=${1:-"$HERE/insearch"}
c++ -arch arm64 -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
  $("$PYTHON_CONFIG" --embed --cflags) \
  -I"$CADICAL_PREFIX/include" "$HERE/insearch.cpp" \
  "$CADICAL_PREFIX/lib/libcadical.a" \
  $("$PYTHON_CONFIG" --embed --ldflags) -o "$OUT"
