#!/usr/bin/env sage -python
"""Independently replay the N53 Bloom pilot's first paired witness stream."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector
from sage.env import SAGE_VERSION

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE_FILE = (ROOT / "experiments/koblitz-cofactor-fiber-20260928"
             / "n53_root_multiplicity_runs/fb244_preflight.json")
ARCHIVE_BASE_FILE = HERE / "replay_base.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def coefficient_row(indices: list[int], labels: list[list[int]], columns: int, r: int) -> list[int]:
    row = [0] * columns
    for index in indices:
        column, weight = labels[index]
        row[column] = (row[column] + weight) % r
    return row


def main() -> None:
    archive = sys.argv[1:] == ["--archive"]
    if sys.argv[1:] and not archive:
        raise SystemExit("usage: replay_sage.py [--archive]")
    receipt = HERE / "independent_sage_replay.json"
    if receipt.exists() and not archive:
        raise FileExistsError(receipt)
    freeze = load(HERE / "freeze_receipt.json")
    summary = load(HERE / "panel_summary.json")
    assert summary["status"] == "verified"
    assert freeze["workload_sha256"] == sha(HERE / "workload.json")
    rows = [json.loads(line) for line in (HERE / "runs/panel_rows.jsonl").read_text().splitlines()]
    assert len(rows) == 10 and summary["rows_sha256"] == sha(HERE / "runs/panel_rows.jsonl")
    manifests = {name: load(HERE / f"{name}_manifest.json") for name in ("reference", "bloom")}
    for name, manifest in manifests.items():
        assert freeze["variants"][name]["manifest_sha256"] == sha(HERE / f"{name}_manifest.json")
        bound = manifest["candidate_freeze"]
        source = (HERE / ("reference.rs" if name == "reference" else "candidate.rs")
                  if archive else Path(bound["source_path"]))
        assert sha(source) == bound["source_sha256"]
        if not archive:
            assert sha(Path(bound["binary_path"])) == bound["binary_sha256"]
    first_runs = {}
    for name in ("reference", "bloom"):
        row = next(row for row in rows if row["pair"] == 1 and row["variant"] == name)
        path = HERE / f"runs/R1_{name}.jsonl"
        assert row["output_sha256"] == sha(path)
        first_runs[name] = load(path)
    reference = first_runs["reference"]
    candidate = first_runs["bloom"]
    assert reference["target_relation_indices"] == candidate["target_relation_indices"]
    assert reference["rank_relation_witnesses"] == candidate["rank_relation_witnesses"]
    assert reference["recovered_scalar"] == candidate["recovered_scalar"]

    record = manifests["bloom"]["identity_record"]
    n = record["field"]["degree"]
    r = record["curve"]["subgroup_order"]
    assert n == 53 and r == 21_044_858_204_113
    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**n, name="z", modulus=t**53 + t**6 + t**2 + t + 1)
    z = field.gen()
    powers = [z**i for i in range(n)]

    def element(word: int):
        result = field(0)
        while word:
            bit = (word & -word).bit_length() - 1
            result += powers[bit]
            word &= word - 1
        return result

    curve = EllipticCurve(field, [field(1), field(0), field(0), field(0), field(1)])

    def point(words: list[int]):
        return curve(element(words[0]), element(words[1]))

    generator = point(record["curve"]["generator"])
    target = point(reference["target"])
    assert r * generator == curve(0) and r * target == curve(0)
    base_file = ARCHIVE_BASE_FILE if archive else BASE_FILE
    base = load(base_file)
    assert base["base_hash"] == reference["factor_base_digest"]
    assert base["base_hash"] == candidate["factor_base_digest"]
    points = [point(coords) for coords in base["factor_base_point_coordinates"]]
    labels = base["factor_base_point_labels"]
    assert len(points) == len(labels) == 25_864
    assert sum((points[i] for i in reference["target_relation_indices"]), curve(0)) == target
    target_row = coefficient_row(reference["target_relation_indices"], labels, 244, r)
    witnesses = reference["rank_relation_witnesses"]
    assert len(witnesses) == reference["rank_attempts_completed"] == 238
    matrix_rows = []
    rhs = []
    for witness in witnesses:
        indices = witness["point_indices"]
        scalar = witness["relation_scalar"]
        assert sum((points[i] for i in indices), curve(0)) == scalar * generator
        matrix_rows.append(coefficient_row(indices, labels, 244, r))
        rhs.append(scalar)
    field_r = GF(r)
    mat = matrix(field_r, matrix_rows)
    assert mat.rank() == reference["rank"] == candidate["rank"] == 237
    combination = mat.transpose().solve_right(vector(field_r, target_row))
    recovered = int(sum(a * b for a, b in zip(combination, rhs))) % r
    assert recovered == reference["recovered_scalar"] == candidate["recovered_scalar"]
    assert recovered * generator == target
    result = {
        "status": "verified",
        "curve_id": record["curve"]["curve_id"],
        "workload_id": freeze["workload_id"],
        "candidate_ids": {name: manifests[name]["candidate_id"] for name in manifests},
        "sage_version": SAGE_VERSION,
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "base_source_sha256": sha(base_file),
        "first_run_output_sha256": {name: sha(HERE / f"runs/R1_{name}.jsonl") for name in manifests},
        "verified_relation_witnesses": len(witnesses),
        "matrix_rank": int(mat.rank()),
        "recovered_scalar": recovered,
        "point_replay": True,
    }
    if archive:
        recorded = load(receipt)
        assert {k: v for k, v in result.items() if k != "sage_version"} == {
            k: v for k, v in recorded.items() if k != "sage_version"
        }
        print(json.dumps({"status": "verified_archival_replay", "sage_version": SAGE_VERSION,
                          "receipt_sha256": sha(receipt)}, sort_keys=True))
    else:
        receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
