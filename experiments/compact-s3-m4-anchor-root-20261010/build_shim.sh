#!/bin/sh
set -eu
q1427_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
q1427_tmp=${Q1427_TMPDIR:-/private/tmp/q1427-clang-tmp}
mkdir -p "$q1427_tmp"
TMPDIR="$q1427_tmp" clang++ -std=c++17 -O2 -fPIC -dynamiclib \
  -I/opt/homebrew/include -L/opt/homebrew/lib \
  -Wl,-rpath,/opt/homebrew/lib -lcryptominisat5 \
  "$q1427_dir/cmsat_stats.cpp" \
  -o "$q1427_dir/libq1427_cmsat_stats.dylib"
