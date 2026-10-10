#!/usr/bin/env python3
"""Independent label reconstruction and finite-matrix receipt audit."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
DOMAIN = GOAL / "n41_w8_two_pair_backward_20261009"
GEOMETRY = GOAL / "n41_w8_fixed_sum_backward_20261009/geometry.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def label(record, states):
    branch, i, j = record[12], record[13], record[14]
    left, right = states[4][i], states[5][j]
    def seven(v):
        if v & 0x20:
            raise ValueError("fixed-zero canonical bit changed")
        return sum(((v >> k) & 1) << (k if k < 5 else k-1) for k in range(8))
    bits = [branch & 1, branch >> 1]
    bits += [(seven(left["a"]) >> k) & 1 for k in range(7)]
    bits += [(seven(right["a"]) >> k) & 1 for k in range(7)]
    bits += [left["sign_a"], left["sign_b"], right["sign_a"], right["sign_b"]]
    return sum(bit << k for k, bit in enumerate(bits))


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first audit")
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    if protocol["source_sha256"] != {path: sha(path) for path in protocol["source_sha256"]}:
        raise ValueError("source or input changed")
    if result["protocol_sha256"] != sha(HERE / "protocol.json") or result["source_sha256"] != protocol["source_sha256"]:
        raise ValueError("result source receipt changed")
    if result["status"] != "FULL_DOMAIN_RANK" or result["charged_structural_ns"] > protocol["cap_ns"]:
        raise ValueError("full-domain rank did not complete inside cap")
    if result["peak_rss_bytes"] > protocol["rss_cap_bytes"]:
        raise ValueError("memory cap exceeded")
    table = (DOMAIN / "table.bin").read_bytes()
    labels = (HERE / "labels.bin").read_bytes()
    geometry = json.loads(GEOMETRY.read_text())
    states = {4: geometry["blocks"][4]["states"], 5: geometry["blocks"][5]["states"]}
    if len(table) != 15 * 99456 or len(labels) != 4 * 99456 or result["labels_sha256"] != sha(HERE / "labels.bin"):
        raise ValueError("table or labels length/hash changed")
    for i in range(99456):
        observed = int.from_bytes(labels[4*i:4*i+4], "little")
        expected = label(table[15*i:15*i+15], states)
        if observed != expected:
            raise ValueError(f"label mismatch at {i}")
    rank = result["rank"]
    if (rank["rows"] != 99456 or rank["label_features"] != 211 or
            rank["mixed_features"] != 1072 or
            rank["mixed_rank_ceiling"] != 861 + rank["label_rank"] or
            rank["x_rank"] > rank["mixed_rank_ceiling"] or
            rank["phi_rank"] > rank["mixed_rank_ceiling"]):
        raise ValueError("rank receipt inconsistent")
    audited = {"status": "PASS_LABEL_AND_RECEIPT_AUDIT", "proposal_id": result["proposal_id"],
               "candidate_id": None, "protocol_sha256": sha(HERE / "protocol.json"),
               "labels_sha256": sha(HERE / "labels.bin"), "checked_labels": 99456,
               "rank": rank}
    output.write_text(json.dumps(audited, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": audited["status"], "checked_labels": 99456, "rank": rank}, sort_keys=True))


if __name__ == "__main__":
    main()
