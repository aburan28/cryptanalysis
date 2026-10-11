"""Exact degree-two feature rank of a fixed-first-pair N131 W15 family."""

import argparse
import hashlib
import importlib.util
import json
import resource
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
AFFINE = GOAL / "n131_w15_family_affine_rank_20261011"
SEEDWISE = GOAL / "n131_w15_seedwise_fouratom_20261011"
SOURCE = GOAL / "n131_w15_coupled_sixpair_20261010"
TRACE = GOAL / "n131_w15_middle_trace_public_gate_20261010/trace_proof.json"
FIELD_N = 131
FEATURE_DIM = 1 + 130 + 130 * 129 // 2
WALL_CAP_SECONDS = 600.0
RSS_CAP_BYTES = 4 * 1024**3


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load("n131_w15_affine_family_prior", AFFINE / "run.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


def source_paths():
    return {"run.py": HERE / "run.py", "affine_run.py": AFFINE / "run.py",
            "affine_protocol.json": AFFINE / "protocol.json",
            "affine_audit.json": AFFINE / "terminal_audit.json",
            "table.tsv": SEEDWISE / "table.tsv",
            "support_w15.tsv": SOURCE / "support_w15.tsv",
            "support_receipt.json": SOURCE / "support_receipt.json",
            "trace_proof.json": TRACE}


def freeze():
    old = json.loads((AFFINE / "protocol.json").read_text())
    trace = json.loads(TRACE.read_text())
    support = json.loads((SOURCE / "support_receipt.json").read_text())
    assert trace["polynomial_basis_trace_support"] == [0, 129]
    assert support["actual_subgroup_factor_base_points_B"] == 197292
    assert old["seed_mask"] == 13686 and old["first_rotation"] == 26
    rows = prior.table()
    assert len(rows) == 8288
    record = {"status": "FROZEN_N131_W15_FIXED_PAIR_QUADRATIC_RANK",
              "curve_id": old["curve_id"], "candidate_id": None,
              "field": "GF(2)[t]/(t^131+t^13+t^2+t+1)",
              "factor_base_B": 197292, "folded_columns_K": 16381,
              "fixed_seed": old["seed_mask"],
              "fixed_first_masks": old["fixed_first_masks"],
              "fixed_first_reciprocal": old["fixed_first_reciprocal"],
              "positive_second_reciprocal": old["positive_second_reciprocal"],
              "positive_four_atom_reciprocal": old["positive_four_atom_reciprocal"],
              "first_rotation": 26, "second_rotation": 39,
              "right_table_rows": len(rows),
              "trace_support": [0, 129],
              "feature_coordinates": "bits 0..128 and 130; bit 129 eliminated by trace zero",
              "feature_order": "constant, 130 linear bits, lexicographic x_i*x_j for i<j",
              "feature_dimension": FEATURE_DIM,
              "wall_cap_seconds": WALL_CAP_SECONDS,
              "rss_cap_bytes": RSS_CAP_BYTES,
              "source_sha256": {name: sha(path) for name, path in source_paths().items()}}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "feature_dimension": FEATURE_DIM}))


def coordinates(z):
    assert (z & 1) == ((z >> 129) & 1)
    return (z & ((1 << 129) - 1)) | (((z >> 130) & 1) << 129)


def feature_row(z):
    x = coordinates(z)
    row = 1 | (x << 1)
    active = x
    while active:
        low = active & -active
        i = low.bit_length() - 1
        active ^= low
        tail = x >> (i + 1)
        start = 131 + 129 * i - i * (i - 1) // 2
        while tail:
            low_tail = tail & -tail
            offset = low_tail.bit_length() - 1
            row |= 1 << (start + offset)
            tail ^= low_tail
    assert row.bit_length() <= FEATURE_DIM
    return row


def rank_insert(basis, row):
    value = row
    while value:
        pivot = value.bit_length() - 1
        if pivot in basis:
            value ^= basis[pivot]
        else:
            basis[pivot] = value
            return True
    return False


def kernel_polynomial(basis):
    """Return one exact degree-two relation when the feature rank is deficient."""
    free = next(bit for bit in range(FEATURE_DIM) if bit not in basis)
    coefficients = 1 << free
    for pivot in sorted(basis):
        if (basis[pivot] & coefficients).bit_count() & 1:
            coefficients |= 1 << pivot
    assert all((row & coefficients).bit_count() % 2 == 0 for row in basis.values())
    return coefficients


def execute():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name, path in source_paths().items()}
    support = {int(a): int(b) for a, b in
               (line.split() for line in (SOURCE / "support_w15.tsv").read_text().splitlines())}
    first_columns = {support[mask] for mask in protocol["fixed_first_masks"]}
    rows = prior.table()
    positive = next(row for row in rows
                    if prior.frob(row[0], 13) == protocol["positive_second_reciprocal"]
                    and {row[1], row[2]} == {3, 13685})
    selected = [positive] + [row for row in rows if row != positive and
                             first_columns.isdisjoint({support[row[1]], support[row[2]]})]
    assert len(selected) <= len(rows) and selected[0] == positive
    start = time.monotonic()
    basis, pivots, rank_progress = {}, [], []
    completed_right = 0
    positive_found = False
    stop = None
    for index, (coordinate, left_mask, right_mask) in enumerate(selected):
        d = prior.frob(coordinate, 13)
        roots = prior.s3_roots(protocol["fixed_first_reciprocal"], d)
        assert roots
        for branch, z in enumerate(roots):
            assert prior.trace(z) == 0
            if index == 0 and z == protocol["positive_four_atom_reciprocal"]:
                positive_found = True
            row = feature_row(z)
            if rank_insert(basis, row):
                pivots.append({"right_index": index,
                               "right_masks": [left_mask, right_mask],
                               "right_reciprocal": d,
                               "branch": branch, "output_z": z})
        completed_right = index + 1
        if completed_right % 256 == 0:
            elapsed = time.monotonic() - start
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rank_progress.append({"right_rows": completed_right,
                                  "output_rows": 2 * completed_right,
                                  "rank": len(basis), "elapsed_seconds": elapsed,
                                  "peak_rss_bytes": rss})
            print(json.dumps(rank_progress[-1]), flush=True)
            if elapsed >= WALL_CAP_SECONDS:
                stop = "WALL_CAP"
            elif rss >= RSS_CAP_BYTES:
                stop = "RSS_CAP"
        if len(basis) == FEATURE_DIM or stop:
            break
    assert positive_found
    kernel = None
    if not stop and completed_right == len(selected) and len(basis) < FEATURE_DIM:
        kernel = kernel_polynomial(basis)
    record = {"status": "COMPLETE_QUADRATIC_RANK" if not stop else "BOUNDED_UNKNOWN",
              "stop_reason": stop, "curve_id": protocol["curve_id"],
              "candidate_id": None, "protocol_sha256": sha(HERE / "protocol.json"),
              "selected_right_rows": len(selected), "right_rows_processed": completed_right,
              "output_rows_processed": 2 * completed_right,
              "feature_dimension": FEATURE_DIM, "rank": len(basis),
              "full_rank": len(basis) == FEATURE_DIM,
              "positive_control_found": positive_found,
              "pivot_witnesses": pivots, "progress": rank_progress,
              "kernel_polynomial_hex": hex(kernel) if kernel is not None else None,
              "elapsed_seconds_exploratory": time.monotonic() - start,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    save(HERE / "result.json", record)
    print(json.dumps({"status": record["status"], "rank": record["rank"],
                      "dimension": FEATURE_DIM,
                      "right_rows_processed": completed_right}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "execute"))
    args = parser.parse_args()
    globals()[args.action]()
