#!/bin/sh
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out=/private/tmp/codex-metal-element-kernel
mkdir -p "$out"
clang++ -std=c++17 -O3 -fPIC -DBH_WITH_METAL \
  -c "$here/source/binary_hardware_cpu.cpp" -o "$out/binary_hardware_cpu.o"
clang++ -std=c++17 -O3 -fPIC -fobjc-arc -DBH_WITH_METAL \
  -c "$here/source/binary_hardware_metal.mm" -o "$out/binary_hardware_metal.o"
clang++ -dynamiclib "$out/binary_hardware_cpu.o" "$out/binary_hardware_metal.o" \
  -framework Foundation -framework Metal -o "$out/libelement.dylib"
shasum -a 256 "$out/libelement.dylib"
