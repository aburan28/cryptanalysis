#!/usr/bin/env python3
"""Evaluate extracted mixed-cubic equations on every frozen unseen pair sum."""

import hashlib
import itertools
import json
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def variable_columns(raw: np.ndarray) -> np.ndarray:
    columns = np.empty((93, len(raw)), dtype=np.bool_)
    for bit in range(6):
        columns[bit] = (raw[:, 0] >> bit) & 1
        columns[6 + bit] = (raw[:, 1] >> bit) & 1
    for bit in range(1, 41):
        columns[11 + bit] = (raw[:, 2 + (bit >> 3)] >> (bit & 7)) & 1
    for bit in range(41):
        columns[52 + bit] = (raw[:, 8 + (bit >> 3)] >> (bit & 7)) & 1
    return columns


def main() -> None:
    output = HERE / "holdout_validation.json"
    if output.exists():
        raise FileExistsError("preserve first held-out validation")
    frozen = json.loads((HERE / "evaluation_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"validation input changed: {name}")
    if digest(Path(__file__)) != frozen["source_sha256"]:
        raise ValueError("evaluation source changed after freeze")
    start = time.monotonic_ns()
    rank = json.loads((HERE / "rank.json").read_text())
    extraction = json.loads((HERE / "equations.json").read_text())
    holdout = json.loads((HERE / "holdout_production.json").read_text())
    if (extraction["rank"] != rank["rank"] or
            extraction["feature_count"] != rank["feature_count"] or
            holdout["rows"] != frozen["holdout_rows"]):
        raise ValueError("rank, extraction, or holdout count changed")
    raw = np.frombuffer((HERE / "holdout.bin").read_bytes(), dtype=np.uint8)
    if len(raw) != frozen["holdout_rows"] * 18:
        raise ValueError("held-out record width changed")
    raw = raw.reshape(-1, 18)
    variables = variable_columns(raw)
    terms = [()]
    terms.extend((i,) for i in range(93))
    terms.extend(itertools.combinations(range(93), 2))
    terms.extend(term for term in itertools.combinations(range(93), 3)
                 if term[0] < 12)
    if len(terms) != 48818:
        raise ValueError("feature enumeration changed")
    scratch = np.empty(len(raw), dtype=np.bool_)
    results = []
    for equation in extraction["equations"]:
        parity = np.zeros(len(raw), dtype=np.bool_)
        for index in equation["support"]:
            term = terms[index]
            if not term:
                np.logical_not(parity, out=parity)
                continue
            np.copyto(scratch, variables[term[0]])
            for bit in term[1:]:
                np.bitwise_and(scratch, variables[bit], out=scratch)
            np.bitwise_xor(parity, scratch, out=parity)
        failures = np.flatnonzero(parity)
        results.append({"free_column": equation["free_column"],
                        "support_size": equation["support_size"],
                        "training_violations": equation["training_violations"],
                        "holdout_violations": int(len(failures)),
                        "first_holdout_violation": int(failures[0]) if len(failures) else None})
    record = {"status": "EVALUATED_FRESH_EXACT_HOLDOUT",
              "curve_id": json.loads((HERE / "protocol.json").read_text())["curve_id"],
              "proposal_id": frozen["proposal_id"],
              "checked_rows": len(raw), "results": results,
              "all_selected_equations_hold": all(r["holdout_violations"] == 0 for r in results),
              "holdout_sha256": digest(HERE / "holdout.bin"),
              "equations_sha256": digest(HERE / "equations.json"),
              "evaluation_source_sha256": digest(Path(__file__)),
              "wall_ns": time.monotonic_ns() - start}
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": record["status"],
                      "holdout_violations": [r["holdout_violations"] for r in results],
                      "wall_s": record["wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
