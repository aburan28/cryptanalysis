#!/usr/bin/env python3
"""Exhaustively audit per-seed gauge opportunity in each radix atlas."""

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys

import model

HERE = Path(__file__).resolve().parent


def main():
    assert sys.argv[1:] in ([], ["--write"])
    atlases = model.atlas_records()
    report = {}
    for label, (atlas, info) in atlases.items():
        groups = defaultdict(lambda: [0, 0, 0])
        for (code,) in struct.iter_unpack("<I", atlas.codes):
            seed_id = code >> 4
            if seed_id:
                exponent = (code >> 3) & 1
                power = (code & 7) // 2
                assert power < 3
                groups[(exponent, seed_id)][power] += 1
        patterns = Counter(tuple(counts) for counts in groups.values())
        baseline = sum(sum(counts) - counts[0] for counts in groups.values())
        optimal = sum(sum(counts) - max(counts) for counts in groups.values())
        assert baseline == optimal
        assert all(a == b == c for a, b, c in groups.values())
        report[label] = {
            "atlas_sha256": info["sha256"],
            "nonidentity_seed_exponent_groups": len(groups),
            "patterns": {",".join(map(str, pattern)): n
                         for pattern, n in sorted(patterns.items())},
            "baseline_uniform_residue_rotations": baseline,
            "optimal_uniform_residue_rotations": optimal,
        }
    result = {
        "schema": 1,
        "status": "exhaustive_atlas_code_audit",
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "atlases": report,
    }
    target = HERE / "gauge-atlas-audit.json"
    if sys.argv[1:] == ["--write"]:
        target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_bytes()) == result
    print(json.dumps({label: data["patterns"] for label, data in report.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
