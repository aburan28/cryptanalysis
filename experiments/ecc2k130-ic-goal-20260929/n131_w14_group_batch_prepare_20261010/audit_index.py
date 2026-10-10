#!/usr/bin/env python3
"""Compare packed S3 indexes, including every source witness and root lift."""

import hashlib
import json
import struct
import sys
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            digest.update(part)
    return digest.hexdigest()


def element(raw, flag_allowed=False):
    assert len(raw) == 17
    top = raw[16]
    assert top & ~15 == 0
    flag = (top >> 3) & 1
    assert flag_allowed or flag == 0
    value = int.from_bytes(raw[:16], "little") | ((top & 7) << 128)
    return value, flag


def read_exact(stream, count):
    value = stream.read(count)
    assert len(value) == count
    return value


def read_index(path):
    with path.open("rb") as stream:
        assert read_exact(stream, 8) == b"S3STRM1\0"
        first, last = struct.unpack("<HH", read_exact(stream, 4))
        for seed in range(first, last+1):
            observed, nl, nr = struct.unpack("<HHH", read_exact(stream, 6))
            assert observed == seed and nl == nr
            left = []
            for _ in range(nl):
                c, _ = element(read_exact(stream, 17))
                h, trace = element(read_exact(stream, 17), True)
                pair, = struct.unpack("<I", read_exact(stream, 4))
                left.append((c, pair, h, trace))
            right = []
            for _ in range(nr):
                c, _ = element(read_exact(stream, 17))
                pair, = struct.unpack("<I", read_exact(stream, 4))
                right.append((c, pair))
            yield seed, left, right
        assert stream.read(1) == b""


def main(new_path, old_path):
    new = list(read_index(new_path))
    assert new
    old = {seed: (left, right) for seed, left, right in read_index(old_path)
           if new[0][0] <= seed <= new[-1][0]}
    assert len(old) == len(new)
    differing_root_choices = 0
    total_entries = 0
    for seed, left, right in new:
        old_left, old_right = old[seed]
        left = sorted(left, key=lambda row: (row[0], row[1]))
        old_left = sorted(old_left, key=lambda row: (row[0], row[1]))
        assert sorted(right) == sorted(old_right)
        assert len(left) == len(old_left)
        for row, prior in zip(left, old_left):
            assert row[:2] == prior[:2]
            assert row[3] == prior[3] == 0
            assert row[2] ^ prior[2] in (0, 1)
            differing_root_choices += row[2] != prior[2]
        total_entries += len(left)
    print(json.dumps({"status": "PASS_COMPLETE_PACKED_INDEX_COMPARISON",
                      "seed_first": new[0][0], "seed_last": new[-1][0],
                      "entries_per_rotation": total_entries,
                      "halftrace_root_choices_differ": differing_root_choices,
                      "new_sha256": sha(new_path), "old_sha256": sha(old_path)},
                     sort_keys=True))


if __name__ == "__main__":
    assert len(sys.argv) == 3
    main(Path(sys.argv[1]), Path(sys.argv[2]))
