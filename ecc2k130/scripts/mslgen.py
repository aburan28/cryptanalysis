#!/usr/bin/env python3
"""Turn the packed GF(2^131) headers into Metal Shading Language source.

The Metal client runs the arithmetic the CUDA and CPU clients run, from the
same headers, so that there is one implementation to hold to the golden model.
The headers are C++ that MSL almost accepts.  What it does not accept is
mechanical, and this script is the whole list:

  - MSL has no #include path at run time: quoted includes are inlined (once
    each), angle-bracket ones dropped (metal_stdlib has the integer types).
  - Every pointer and reference needs an address space.  Operands passed as
    `const P131 &` go by value; the walk's tables are `device` memory; every
    other pointer in these headers is to a local, `thread`.
  - `unsigned long long` is `ulong`, __builtin_popcount is popcount,
    namespace-scope constants are `constant`, and `#pragma unroll` means
    nothing to this compiler.

The output is a C++ raw string literal holding prologue + headers + kernels,
which src/metalwalk.h compiles with newLibraryWithSource when the client
starts: no offline Metal toolchain (full Xcode) is needed to build or run.

usage: mslgen.py <include dir> <kernel.metal> <out.inc>
"""
import re
import sys
from pathlib import Path

# The kernel's configuration on a GPU with no carry-less multiplier: the
# generated masked-multiply product, the direct reduction, the reduced
# conversion, and the byte-table selection layout every client shares.
PROLOGUE = """#include <metal_stdlib>
using namespace metal;
#define ECC_HOST_CLMUL 0
#define ECC_PACKED_CLMAD 0
#define ECC_PACKED_GENERATED_PRODUCT 1
#define ECC_PACKED_DIRECT_REDUCE 1
#define ECC_PACKED_FROM_REDUCED 1
#define ECC_PACKED_SINGLE_PRODUCT 1
#define ECC_PACKED_BY_VALUE 1
#define ECC_PACKED_UNROLL_INV 1
#define ECC_PACKED_ALU_SQUARE 1
#define ECC_PACKED_ALU_SQR 1
#define ECC_PACKED_INLINE_POLY 3
#define ECC_PACKED_PERM_SIGMA 0
#define ECC_WALK_TABLE 1
#define ECC_TABLE_PIVOT_BYTES 1
"""

# Headers whose pointers are all into the walk's tables.
TABLE_HEADERS = {"packedtablewalk.cuh"}
# Included only under knobs the prologue leaves off: the host multiplier and the
# two-stage reduction.  The Frobenius permutation networks (packedsigma131.h)
# are inlined, masks in the constant address space, so that
# ECC_PACKED_PERM_SIGMA can be tried on a Mac; the prologue still leaves it off.
SKIPPED_HEADERS = {"hostclmul.h", "packedpolyreduce131.h"}


def inline_includes(path, include_dir, seen):
    if path.name in seen:
        return ""
    seen.add(path.name)
    out = []
    for line in path.read_text().splitlines():
        m = re.match(r'\s*#\s*include\s+"([^"]+)"', line)
        if m and Path(m.group(1)).name in SKIPPED_HEADERS:
            continue
        if m:
            out.append(transform(include_dir / Path(m.group(1)).name, include_dir, seen))
        elif re.match(r"\s*#\s*include\s+<", line) or re.match(r"\s*#\s*pragma\s+(once|unroll)", line):
            continue
        else:
            out.append(line)
    return "\n".join(out)


def transform(path, include_dir, seen):
    text = inline_includes(path, include_dir, seen)
    if not text:
        return text
    space = "device" if path.name in TABLE_HEADERS else "thread"
    # operands by value
    text = re.sub(r"const\s+P131\s*&\s*(\w+)", r"P131 \1", text)
    # array parameters of the carry-less helpers are pointers to locals (on
    # signature lines only: a local `uint32_t lo[4], hi[4];` must stay an array)
    text = re.sub(r"(?m)^ECC_HD .*$",
                  lambda m: re.sub(r"\b(const\s+)?uint32_t\s+(\w+)\[\d+\](?=\s*[,)])",
                                   r"\1thread uint32_t *\2", m.group(0)), text)
    # out-parameters and the step history are locals of the caller
    text = re.sub(r"\bP131\s*\*\s*(\w+)", r"thread P131 *\1", text)
    text = re.sub(r"\bunsigned long long\s*\*\s*(\w+)", r"thread ulong *\1", text)
    # remaining word and byte pointers: tables in the table header, locals elsewhere
    text = re.sub(r"(?<!thread )\b(const\s+)?(uint32_t|uint8_t)\s*\*", rf"\1{space} \2 *", text)
    # namespace-scope constants live in the constant address space
    text = re.sub(r"(?m)^static const (int|size_t) ", r"constant \1 ", text)
    # the permutation networks' mask tables
    text = text.replace("alignas(32) static const", "constant")
    text = text.replace("unsigned long long", "ulong")
    text = text.replace("__builtin_popcount", "popcount")
    return text


def main():
    include_dir, kernel, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    seen = set()
    parts = [PROLOGUE]
    for header in ("packed131.h", "packedtablewalk.cuh"):
        parts.append(transform(include_dir / header, include_dir, seen))
    parts.append(kernel.read_text())
    source = "\n".join(parts)
    delim = "ECCMSL"
    assert f"){delim}\"" not in source
    # One literal would exceed what some compilers accept; adjacent pieces concatenate.
    lines = source.splitlines(keepends=True)
    chunks = ["".join(lines[i:i + 200]) for i in range(0, len(lines), 200)]
    out.write_text("".join(f'R"{delim}({c}){delim}"\n' for c in chunks))
    # The same source as a file, for EC2K_METAL_SOURCE and for reading.
    out.with_suffix(".metal").write_text(source)


if __name__ == "__main__":
    main()
