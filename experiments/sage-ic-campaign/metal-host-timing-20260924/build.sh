#!/bin/sh
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out=/private/tmp/codex-metal-host-timing
mkdir -p "$out"
clang++ -std=c++17 -O3 -fPIC -DBH_WITH_METAL \
  -c "$here/source/binary_hardware_cpu.cpp" -o "$out/binary_hardware_cpu.o"
clang++ -std=c++17 -O3 -fPIC -fobjc-arc -DBH_WITH_METAL \
  -c "$here/source/instrumented_metal.mm" -o "$out/instrumented_metal.o"
clang++ -dynamiclib "$out/binary_hardware_cpu.o" "$out/instrumented_metal.o" \
  -framework Foundation -framework Metal -o "$out/libinstrumented.dylib"
shasum -a 256 "$out/libinstrumented.dylib"
