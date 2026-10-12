#!/usr/bin/env python3
"""Replay source-bound ordinary Q1463 WDSat receipts and any SAT relation."""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1419 = PARENT / "q1419_partial_pin"
sys.path.insert(0, str(Q1419))
from verify_archive import check_serialized_xcnf  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    builder_path = PARENT / "q20261011_wdsat_shared_prefix/build_receipt.json"
    builder = json.loads(builder_path.read_text())
    q1419_protocol = json.loads((Q1419 / "protocol.json").read_text())
    assert protocol["proposal_id"] == freeze["proposal_id"] == "Q1463"
    assert protocol["candidate_id"] is freeze["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["prepare_source_sha256"] == sha(HERE / "prepare.py")
    assert freeze["adapter_source_sha256"] == sha(PARENT / "q20261011_wdsat_shared_prefix/prepare.py")
    equivalence_path = PARENT / "q20261011_wdsat_shared_prefix/equivalence_check.json"
    equivalence = json.loads(equivalence_path.read_text())
    assert equivalence["status"] == "PASS"
    assert equivalence["transform_source_sha256"] == freeze["adapter_source_sha256"]
    assert freeze["adapter_equivalence_check_sha256"] == sha(equivalence_path)
    assert freeze["builder_receipt_sha256"] == sha(builder_path)
    rows = []
    for degree in (53, 83):
        name = f"n{degree}"
        record = freeze["cells"][name]
        source = PARENT / "runs" / f"{name}_q{1410 if degree == 53 else 1408}_ordinary"
        derived_archive = HERE / f"{name}_ordinary.xcnf.gz"
        original_archive = source.with_suffix(".xcnf.gz")
        assert sha(derived_archive) == record["derived_archive_sha256"]
        assert sha(original_archive) == record["source_archive_sha256"]
        assert sha(source.with_suffix(".json")) == record["source_receipt_sha256"]
        derived = gzip.decompress(derived_archive.read_bytes())
        original = gzip.decompress(original_archive.read_bytes())
        assert hashlib.sha256(derived).hexdigest() == record["derived_raw_sha256"]
        assert hashlib.sha256(original).hexdigest() == record["source_raw_sha256"]
        profile = q1419_protocol["profiles"][str(degree)]
        assert profile["curve_id"] == record["curve_id"]
        # Q1419 supplies the same curve/base geometry with a separate target.
        assert profile["factor_base_actual_B"] == record["factor_base_actual_B"]
        assert profile["folded_columns_K"] == record["factor_base_folded_columns_K"]
        assert profile["factor_base_enumerated_set_sha256"] == record["factor_base_enumerated_set_sha256"]
        for variant in protocol["solver"]["variants"]:
            run_dir = HERE / "runs" / name / variant
            if not (run_dir / "receipt.json").exists():
                continue
            receipt = json.loads((run_dir / "receipt.json").read_text())
            stdout = (run_dir / "solver.stdout.txt").read_bytes()
            stderr = (run_dir / "solver.stderr.txt").read_bytes()
            binary = builder["per_degree"][name]
            assert receipt["proposal_id"] == "Q1463"
            assert receipt["candidate_id"] is receipt["run_id"] is None
            assert receipt["isogeny"] == "none" and receipt["ordinary_query"] is True
            assert receipt["degree"] == degree and receipt["variant"] == variant
            assert receipt["curve_id"] == record["curve_id"]
            assert receipt["workload_id"] == record["workload_id"]
            assert receipt["public_target"] == record["public_target"]
            assert receipt["factor_base_actual_B"] == record["factor_base_actual_B"]
            assert receipt["factor_base_folded_columns_K"] == record["factor_base_folded_columns_K"]
            assert receipt["factor_base_enumerated_set_sha256"] == record["factor_base_enumerated_set_sha256"]
            assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
            assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
            assert receipt["runner_sha256"] == sha(HERE / "run.py")
            assert receipt["builder_receipt_sha256"] == sha(builder_path)
            assert receipt["source_archive_sha256"] == sha(original_archive)
            assert receipt["derived_archive_sha256"] == sha(derived_archive)
            assert receipt["binary_sha256"] == binary["binary_sha256"] == sha(Path(binary["binary_path"]))
            assert receipt["stdout_sha256"] == hashlib.sha256(stdout).hexdigest()
            assert receipt["stderr_sha256"] == hashlib.sha256(stderr).hexdigest()
            error_text = stderr.decode("utf-8", "replace")
            assert receipt["after_xor_init"] == ("Q1458_AFTER_XOR_INIT" in error_text)
            assert receipt["search_started"] == ("Q1458_SEARCH_START" in error_text)
            assert receipt["complete_solve_work_log2"] is None
            assert receipt["natural_relation_yield_estimate"] is None
            assert receipt["wall_limit_seconds"] == protocol["limits"]["wall_seconds_per_attempt"]
            relation = None
            if receipt["status"] == "SAT_REPLAYED_XCNF":
                variables = record["transform_stats"]["derived_variables"]
                models = [line for line in stdout.decode("ascii").splitlines()
                          if len(line) == variables and set(line) <= {"0", "1"}]
                assert len(models) == receipt["model_count"] == 1
                model = {i + 1: value == "1" for i, value in enumerate(models[0])}
                original_model = {key: value for key, value in model.items()
                                  if key <= record["transform_stats"]["original_variables"]}
                for raw, witness, key in ((derived, model, "derived"),
                                           (original, original_model, "original")):
                    replay = check_serialized_xcnf(raw, witness)
                    assert all(receipt["model_replay"][key][field] == value
                               for field, value in replay.items())
                # The group check is done by checked Sage in replay_relation.py.
                relation = "pending_checked_sage_replay"
            elif receipt["status"] == "BOUNDED_UNKNOWN":
                assert receipt["timed_out"] and receipt["search_started"]
                assert receipt["model_replay"] is None
                assert receipt["verified_natural_relations"] == 0
            else:
                assert receipt["status"] in ("CENSORED_BEFORE_SEARCH", "PRODUCER_FAILURE",
                                              "UNSAT_REPORTED_UNVERIFIED", "MODEL_REPLAY_FAILED",
                                              "PRODUCER_FAILURE_NO_MODEL")
            rows.append({"degree": degree, "variant": variant,
                         "status": receipt["status"], "search_started": receipt["search_started"],
                         "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                         "user_cpu_seconds": receipt["user_cpu_seconds"],
                         "maxrss_child_bytes_darwin": receipt["maxrss_child_bytes_darwin"],
                         "relation_replay": relation, "receipt_sha256": sha(run_dir / "receipt.json")})
    output = {"proposal_id": "Q1463", "candidate_id": None, "status": "PASS",
              "freeze_sha256": sha(HERE / "freeze.json"), "runs": rows,
              "complete_solve_work_log2": None}
    (HERE / "verification.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("PASS Q1463", len(rows), "runs")


if __name__ == "__main__":
    main()
