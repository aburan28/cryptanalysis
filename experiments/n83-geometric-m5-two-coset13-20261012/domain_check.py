#!/usr/bin/env python3
"""Independent finite-domain check for the generalized affine leaf map."""

import hashlib
import json
from pathlib import Path

from run import field, in_rotated_affine_seed

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "domain_check.json"
    assert not output.exists(), "refusing to overwrite evidence"
    protocol = json.loads((HERE / "protocol.json").read_text())
    row = protocol["base_rows"][0]
    onb = field.Onb(83)
    offset = row["offset_onb_coordinates"]
    basis = row["basis_onb_coordinates"]
    delta = basis[12]
    seeds = {offset ^ (c & 4095) ^ ((c >> 12) * delta)
             for c in range(8192)}
    assert len(seeds) == 8192
    for seed in seeds:
        assert in_rotated_affine_seed(onb, seed, 13, offset, basis)
    sampled = 0
    for coefficient in range(0, 8192, 257):
        x = offset ^ (coefficient & 4095) ^ ((coefficient >> 12) * delta)
        for power in range(83):
            rotated = onb.toCoords(onb.frob(onb.fromCoords(x), power))
            assert in_rotated_affine_seed(onb, rotated, 13, offset, basis)
            sampled += 1
    report = {
        "kind": "n83_two_coset_affine_leaf_domain_check_v1",
        "status": "PASS",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "runner_sha256": sha(HERE / "run.py"),
        "distinct_affine_seeds": len(seeds),
        "all_affine_seed_memberships": "PASS",
        "sampled_rotated_seed_memberships": sampled,
    }
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
