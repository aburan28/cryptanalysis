#!/usr/bin/env python3
"""Regenerate the frozen query stream and count identity-pair exceptions."""
from __future__ import annotations
import hashlib
import json
import random
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "q20261011_n53_native_pair"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    freeze = json.loads((HERE / "freeze.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    measured = json.loads((HERE / "native_measurement.json").read_text())
    base_file = PRIOR / "inputs/base.bin"
    assert sha(base_file) == freeze["base_input_sha256"]
    raw = base_file.read_bytes()
    base = [(int.from_bytes(raw[i:i+16], "little"),
             int.from_bytes(raw[i+16:i+32], "little"))
            for i in range(0, len(raw), 32)]
    assert len(base) == protocol["factor_base_actual_B"]
    rng = random.Random(protocol["point_decomposition"]["query_seed"])
    caps = protocol["point_decomposition"]["query_caps"]
    prefix = hashlib.sha256()
    full = hashlib.sha256()
    identity_count = 0
    counts = {}
    for i in range(1, caps[-1]+1):
        a = rng.randrange(len(base)); b = rng.randrange(len(base))
        pair = struct.pack("<HH", a, b)
        full.update(pair)
        if i <= caps[0]:
            prefix.update(pair)
        x0,y0 = base[a]; x1,y1 = base[b]
        identity_count += x0 == x1 and (y0 ^ y1) == x0
        if i in caps:
            counts[str(i)] = identity_count
    assert prefix.hexdigest() == freeze["prefix_1500000_sha256"]
    assert full.hexdigest() == freeze["query_file_sha256"]
    assert identity_count == measured["query_skipped_identity_pairs"]
    output = {"status": "PASS", "proposal_id": "Q1456", "candidate_id": None,
              "run_id": None, "curve_id": protocol["curve_id"],
              "workload_id": protocol["workload_id"], "isogeny": "none",
              "query_seed": protocol["point_decomposition"]["query_seed"],
              "query_count": caps[-1], "query_sha256": full.hexdigest(),
              "prefix_1500000_sha256": prefix.hexdigest(),
              "identity_pair_prefix_counts": counts,
              "source_sha256": sha(Path(__file__))}
    (HERE / "query_prefix_audit.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("PASS Q1456 query stream", counts)


if __name__ == "__main__":
    main()
