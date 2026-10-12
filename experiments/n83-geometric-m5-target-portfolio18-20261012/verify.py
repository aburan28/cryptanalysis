#!/usr/bin/env python3
"""Audit one-target fixed-preimage portfolio and all bounded attempts."""

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101255"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["target_choices"] == [1, 2, 3, 4, 5, 7, 11, 19,
                                           37, 73, 147, 267]
    assert protocol["limits"]["total_wall_seconds"] == 600
    assert protocol["limits"]["per_choice_wall_seconds"] == 50
    assert protocol["solver"]["threads"] == 1
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(Path(protocol["solver"]["path"])) == protocol[
        "solver"]["sha256"]
    assert sha(SOURCE / "protocol.json") == protocol["parent_protocol_sha256"]
    assert sha(SOURCE / "width18_ordinary.json") == protocol[
        "parent_result_sha256"]
    assert sha(SOURCE / "sage_relation_replay.json") == protocol[
        "parent_sage_replay_sha256"]
    assert sha(SOURCE / "karatsuba_control.json") == protocol[
        "parent_control_sha256"]
    assert json.loads((SOURCE / "karatsuba_control.json").read_text())[
        "status"] == "PASS"
    row = protocol["base_rows"][0]
    assert row["dimension"] == 18
    assert row["B"] == 21714958 and row["K"] == 130813
    assert sha(ROOT / row["base_file"]) == row["base_sha256"]
    assert sha(ROOT / row["canonical_x_cache_file"]) == row[
        "canonical_x_cache_sha256"]
    result_path = HERE / "portfolio_ordinary.json"
    result = json.loads(result_path.read_text())
    assert result["proposal_id"] == protocol["proposal_id"]
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["runner_sha256"] == sha(HERE / "portfolio.py")
    assert result["field_multiplier_selfcheck"]["status"] == "PASS"
    assert result["curve_id"] == protocol["curve_id"]
    assert result["workload_id"] == protocol["workload_id"]
    assert result["public_point_onb_raw"] == protocol[
        "workload"]["public_point_onb_raw"]
    assert result["B"] == row["B"] and result["K"] == row["K"]
    assert result["base_sha256"] == row["base_sha256"]
    assert result["canonical_x_cache_sha256"] == row[
        "canonical_x_cache_sha256"]
    assert result["raw_target_preimage_count"] == 332
    assert result["target_choices_planned"] == protocol["target_choices"]
    attempted = result["target_choices_attempted"]
    assert attempted == protocol["target_choices"][:len(attempted)]
    assert 1 <= len(attempted) <= len(protocol["target_choices"])
    assert [a["choice"] for a in result["attempts"]] == attempted
    assert [a["status"] for a in result["attempts"]] == [
        "external_timeout"] * 12
    assert all(not a["model_present"] for a in result["attempts"])
    assert result["status"] in ("verified_relation", "bounded_unknown")
    assert (result["verified_relation"] is not None) == (
        result["status"] == "verified_relation")
    if result["verified_relation"] is not None:
        assert result["verified_relation"]["status"] == "verified_five_point_relation"
        assert result["verified_relation"]["choice"] == attempted[-1]
    phases = result["online_pdp_phase_ns"]
    assert abs(sum(phases.values()) - result[
        "online_pdp_wall_ns_exploratory"]) < 1_000_000
    assert 600_000_000_000 <= result[
        "online_pdp_wall_ns_exploratory"] < 602_000_000_000
    for attempt in result["attempts"]:
        assert 0 <= attempt["choice"] < 332
        assert attempt["formula_shape"]["and_gates"] == 12174
        assert attempt["formula_shape"]["cnf_clauses"] == 105251
        assert attempt["stdout_sha256"] == sha(HERE / attempt["stdout_file"])
        assert attempt["stderr_sha256"] == sha(HERE / attempt["stderr_file"])
        compressed = HERE / attempt["xcnf_gzip"]
        assert attempt["xcnf_gzip_sha256"] == sha(compressed)
        with gzip.open(compressed, "rb") as stream:
            raw = stream.read()
        assert len(raw) == attempt["xcnf_raw_bytes"]
        assert hashlib.sha256(raw).hexdigest() == attempt["xcnf_raw_sha256"]
    print(json.dumps({"status": "PASS", "proposal_id": protocol["proposal_id"],
                      "ordinary_status": result["status"],
                      "attempted": attempted,
                      "verified_relation": result["verified_relation"] is not None},
                     sort_keys=True))


if __name__ == "__main__":
    main()
