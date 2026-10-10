#!/usr/bin/env python3
"""Independent bitset rank witnesses for the N41 conditional-affine screen."""

import hashlib
import json
import struct
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
DIM = 1072
LABEL_DIM = 211
COUNT = 99456


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mask_bits(state):
    value = state["a"]
    if value >= 256 or value & 32:
        raise ValueError("unexpected mask bit 5")
    return [((value >> source) & 1) for source in (0, 1, 2, 3, 4, 6, 7)]


def label_bits(record, states):
    branch, i, j = record[12], record[13], record[14]
    left, right = states[4][i], states[5][j]
    return ([branch & 1, (branch >> 1) & 1] + mask_bits(left) + mask_bits(right) +
            [left["sign_a"], left["sign_b"], right["sign_a"], right["sign_b"]])


def label_row(bits):
    row = 1
    for bit in range(20):
        if bits[bit]:
            row |= 1 << (1 + bit)
    column = 21
    for a in range(20):
        for b in range(a + 1, 20):
            if bits[a] and bits[b]:
                row |= 1 << column
            column += 1
    if column != LABEL_DIM:
        raise AssertionError(column)
    return row


def mixed_row(labels, label_feature_row, coordinate):
    row = label_feature_row
    active_labels = [bit for bit, value in enumerate(labels) if value]
    for c in range(41):
        if (coordinate >> c) & 1:
            row |= 1 << (LABEL_DIM + c)
            for bit in active_labels:
                row |= 1 << (LABEL_DIM + 41 + c * 20 + bit)
    return row


def add(basis, row):
    while row:
        pivot = row.bit_length() - 1
        other = basis.get(pivot)
        if other is None:
            basis[pivot] = row
            return True
        row ^= other
    return False


def main():
    result_path = HERE / "independent_rank.json"
    if result_path.exists():
        raise FileExistsError(result_path)
    table_path = GOAL / "n41_w8_two_pair_backward_20261009/table.bin"
    phi_path = GOAL / "n41_two_pair_residual_degree3_20261009/phi.bin"
    geometry_path = GOAL / "n41_w8_fixed_sum_backward_20261009/geometry.json"
    producer = json.loads((HERE / "result.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    if producer["status"] != "FULL_DOMAIN_RANK" or producer["protocol_sha256"] != sha(HERE / "protocol.json"):
        raise ValueError("producer or protocol changed")
    for path in (table_path, phi_path, geometry_path):
        if protocol["source_sha256"][str(path)] != sha(path):
            raise ValueError(f"input changed: {path}")
    table = table_path.read_bytes()
    phi = phi_path.read_bytes()
    if len(table) != COUNT * 15 or len(phi) != COUNT * 6:
        raise ValueError("input length changed")
    geometry = json.loads(geometry_path.read_text())
    states = {k: geometry["blocks"][k]["states"] for k in (4, 5)}
    bases = {"labels": {}, "x": {}, "phi": {}}
    witnesses = {"labels": [], "x": [], "phi": []}
    start = time.monotonic_ns()
    processed = 0
    for k in range(20000):
        # Interleave all four target branches and permute within each branch.
        index = (k % 4) * 24864 + (((k // 4) * 977 + 13) % 24864)
        record = table[index*15:index*15+15]
        labels = label_bits(record, states)
        label_feature_row = label_row(labels)
        coordinates = {
            "x": int.from_bytes(record[:6], "little"),
            "phi": int.from_bytes(phi[index*6:index*6+6], "little"),
        }
        rows = {"labels": label_feature_row,
                "x": mixed_row(labels, label_feature_row, coordinates["x"]),
                "phi": mixed_row(labels, label_feature_row, coordinates["phi"])}
        for kind, row in rows.items():
            if add(bases[kind], row):
                witnesses[kind].append(index)
        processed += 1
        if (len(bases["labels"]) == LABEL_DIM and
                len(bases["x"]) == DIM and len(bases["phi"]) == DIM):
            break
    for kind, indices in witnesses.items():
        path = HERE / f"{kind}_witness.bin"
        path.write_bytes(struct.pack("<" + "I" * len(indices), *indices))
    outcome = {
        "status": "FULL_INDEPENDENT_RANK" if len(bases["labels"]) == LABEL_DIM and len(bases["x"]) == DIM and len(bases["phi"]) == DIM else "RANK_BELOW_DIM_WITHIN_CAP",
        "ranks": {kind: len(bases[kind]) for kind in bases},
        "rows_processed": processed,
        "time_ns": time.monotonic_ns() - start,
        "source_sha256": sha(__file__),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "table_sha256": sha(table_path), "phi_sha256": sha(phi_path),
        "geometry_sha256": sha(geometry_path),
        "witness_sha256": {kind: sha(HERE / f"{kind}_witness.bin") for kind in witnesses},
    }
    result_path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: outcome[key] for key in ("status", "ranks", "rows_processed", "time_ns")}, sort_keys=True))


if __name__ == "__main__":
    main()
