#!/usr/bin/env python3
"""Check frozen Q1423 inputs, all eight archived XCNFs and solver logs."""

import gzip
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "experiments/compact-s3-m4-20261003"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha(Path(path).read_bytes())


def main():
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert frozen["proposal_id"] == "Q1423"
    assert frozen["protocol_sha256"] == digest(HERE / "PROTOCOL.md")
    assert frozen["builder_sha256"] == digest(HERE / "fixed_leaf.py")
    assert frozen["runner_sha256"] == digest(HERE / "run.py")
    assert frozen["solver_binary_sha256"] == digest(frozen["solver_binary"])
    for path, expected in frozen["old_source_sha256"].items():
        assert digest(OLD / path) == expected
    for path, expected in frozen["root_source_sha256"].items():
        assert digest(ROOT / path) == expected
    for path, expected in frozen["input_sha256"].items():
        assert digest(OLD / path) == expected
    sage = json.loads((HERE / "verification_sage.json").read_text())
    assert sage["status"] == "PASS"
    assert {row["field_degree"] for row in sage["cases"]} == {53, 83}
    rows = []
    for n in (53, 83):
        case = frozen["cases"][str(n)]
        for mode in ("locked", "control_unpinned", "pool1", "pool64"):
            stem = f"n{n}_{mode}"
            receipt_path = HERE / (stem + ".json")
            receipt = json.loads(receipt_path.read_text())
            assert receipt["freeze_sha256"] == digest(HERE / "freeze.json")
            assert receipt["curve_id"] == case["curve_id"]
            assert receipt["factor_base_actual_B"] == case["actual_B"]
            assert receipt["factor_base_folded_columns_K"] == case["folded_K"]
            assert receipt["factor_base_enumerated_set_sha256"] == case["base_digest"]
            assert receipt["workload_id"] == (case["ordinary_workload_id"]
                                              if mode.startswith("pool") else None)
            sage_case = next(row for row in sage["cases"]
                             if row["field_degree"] == n)
            if mode != "locked":
                sage_selection = next(row for row in sage_case["selected_modes"]
                                      if row["mode"] == mode)
                assert sage_selection["receipt_sha256"] == digest(receipt_path)
            formula_meta = receipt["formula_archive"]
            packed = HERE / formula_meta["path"]
            assert digest(packed) == formula_meta["compressed_sha256"]
            formula = gzip.decompress(packed.read_bytes())
            assert sha(formula) == formula_meta["sha256"]
            assert len(formula) == formula_meta["uncompressed_bytes"]
            head = formula.split(b"\n", 1)[0].split()
            assert head[:2] == [b"p", b"cnf"]
            assert int(head[2]) == receipt["formula"]["variables"]
            assert int(head[3]) == (receipt["formula"]["cnf_clauses"] +
                                    receipt["formula"]["xor_rows"])
            streams = {}
            for channel in ("stdout", "stderr"):
                meta = receipt["solver"]["logs"][channel]
                archive = HERE / meta["path"]
                assert digest(archive) == meta["compressed_sha256"]
                data = gzip.decompress(archive.read_bytes())
                assert sha(data) == meta["sha256"]
                assert len(data) == meta["uncompressed_bytes"]
                streams[channel] = data.decode("utf-8", "replace")
            solver = receipt["solver"]
            assert solver["search_began"]
            status = re.findall(r"^s\s+(\S+)", streams["stdout"], re.M)
            conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)",
                                   streams["stdout"], re.M)
            if solver["conflicts"] is not None:
                assert int(conflicts[-1]) == solver["conflicts"]
            if mode == "locked":
                assert solver["status"] == "SAT" and solver["return_code"] == 10
                assert status[-1] == "SATISFIABLE"
                assert receipt["formula_model_checked"]
                assert receipt["lift_status"] == "verified_four_point_relation"
                assert sage_case["receipt_sha256"] == digest(receipt_path)
            else:
                assert solver["status"] == "BOUNDED_UNKNOWN"
                assert receipt["verified_relation"] is None
                if solver["stop_reason"] is None:
                    assert status[-1] == "INDETERMINATE"
                    assert solver["conflicts"] >= frozen["search"]["max_conflicts"]
                else:
                    assert solver["stop_reason"] == "external_timeout"
                    assert solver["wall_seconds"] >= frozen["search"]["external_seconds"]
            rows.append({"stem": stem, "status": solver["status"],
                         "stop_reason": solver["stop_reason"],
                         "conflicts": solver["conflicts"],
                         "formula_sha256": formula_meta["sha256"]})
    result = {"schema": "q1423-archive-verification-v1", "status": "PASS",
              "freeze_sha256": digest(HERE / "freeze.json"), "rows": rows,
              "sage_verification_sha256": digest(HERE / "verification_sage.json"),
              "verifier_sha256": digest(__file__)}
    (HERE / "verification.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
