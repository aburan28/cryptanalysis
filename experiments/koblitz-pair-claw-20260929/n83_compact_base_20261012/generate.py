#!/usr/bin/env python3
"""Patch the frozen native N83 source to reconstruct base points on access."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent
sys.path.insert(0, str(PAIR))

import bench_n83_zero_run_stage as zero_stage  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    assert source.count(old) == 1, old[:80]
    return source.replace(old, new)


def generate(directory):
    assert all(sha(path) == digest for path, digest in zero_stage.FROZEN.items())
    directory.mkdir(parents=True, exist_ok=True)
    pairs, core, main = zero_stage.generated_sources(directory)
    source = pairs.read_text()
    begin = source.index("std::vector<Point> load_base(")
    end = source.index("struct BatchScratch {", begin)
    assert source[begin:end].count("return result;") == 1
    source = (source[:begin] + '#include "compact_base.inc"\n\n' +
              source[end:])
    source = replace_once(source,
                          "void self_test(const std::vector<Point> &base)",
                          "void self_test(const CompactBase &base)")
    source = replace_once(source,
                          "Result measure(const std::vector<Point> &base,",
                          "Result measure(const CompactBase &base,")
    pairs.write_text(source)
    main_source = replace_once(main.read_text(),
                               "void signed_x_self_test(const std::vector<Point> &base,",
                               "void signed_x_self_test(const CompactBase &base,")
    main.write_text(main_source)
    include = directory / "compact_base.inc"
    include.write_bytes((HERE / "compact_base.inc").read_bytes())
    header = directory / "eccF83.h"
    header.write_bytes(zero_stage.HEADER.read_bytes())
    return {path.name: sha(path) for path in (pairs, core, main, include, header)}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate.py OUTPUT_DIR")
    directory = Path(sys.argv[1]).resolve()
    assert not directory.exists(), "source bundle already exists"
    hashes = generate(directory)
    print(json.dumps(hashes, sort_keys=True))


if __name__ == "__main__":
    main()
