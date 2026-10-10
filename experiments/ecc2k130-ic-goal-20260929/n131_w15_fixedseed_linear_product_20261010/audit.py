#!/usr/bin/env python3
"""Audit the fixed-seed linear product control and bounded extraction."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_coupled_sixpair_20261010"
SOURCE = HERE.parent / "n131_w15_one_seed_public_gate_20261010"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text())


def formula(path, profile):
    digest = hashlib.sha256()
    size = cnf = xor = 0
    with gzip.open(path, "rb") as stream:
        header = next(stream)
        assert header == f"p cnf {profile['variables']} {profile['clauses']+profile['xor_rows']}\n".encode()
        digest.update(header)
        size += len(header)
        for line in stream:
            digest.update(line)
            size += len(line)
            if line.startswith(b"x"):
                xor += 1
            else:
                cnf += 1
    assert digest.hexdigest() == profile["sha256"]
    assert size == profile["bytes"]
    assert cnf == profile["clauses"] and xor == profile["xor_rows"]
    return {"sha256": digest.hexdigest(), "bytes": size,
            "variables": profile["variables"], "clauses": cnf, "xor_rows": xor}


def main():
    protocol = load(HERE / "protocol.json")
    control = load(HERE / "control.json")
    result = load(HERE / "result.json")
    identity = load(HERE / "product_identity.json")
    baseline = load(BASE / "control_result.json")["formula"]
    prior_pin = load(SOURCE / "control.json")
    assert protocol["status"] == "FROZEN_W15_FIXEDSEED_LINEAR_PRODUCT_CONTROL"
    assert control["status"] == "PASS_LINEAR_PRODUCT_CONSTRUCTED_WITNESS"
    assert identity["status"] == "PASS_ALL_32768_FIXED_SEED_PRODUCTS"
    assert identity["product_image_dimension"] == 14
    assert identity["tested_left_masks"] == 32768
    assert protocol["target_count"] == result["target_count"] == 0
    assert protocol["target_q"] == result["target_q"] == control["target_q"]
    assert result["sha256"]["protocol"] == control["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["sha256"]["control"] == sha(HERE / "control.json")
    assert result["sha256"]["stdout"] == sha(HERE / "solver.stdout.txt")
    assert result["sha256"]["stderr"] == sha(HERE / "solver.stderr.txt")
    assert result["sha256"]["formula_gzip"] == sha(HERE / "system.xcnf.gz")
    assert result["pin_clauses"] == control["pin_clauses"] == prior_pin["pin_clauses"]
    assert result["formula"] == control["formula"]
    assert control["xcnf_check"] == {"cnf_clauses": 424401, "xor_rows": 43218}
    current = result["formula"]
    assert baseline["variables"] - current["variables"] == 4172
    assert baseline["clauses"] + 30 - current["clauses"] == 12354
    assert baseline["xor_rows"] - current["xor_rows"] == 54
    assert baseline["and_gates"] - current["and_gates"] == 4118
    assert result["phase_seconds"]["construction_plus_search"] <= protocol["construction_plus_search_cap_seconds"]
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    checked_formula = formula(HERE / "system.xcnf.gz", current)
    stdout = (HERE / "solver.stdout.txt").read_text(errors="replace")
    statuses = [line for line in stdout.splitlines() if line.startswith("s ")]
    assert statuses == result["solver_status_lines"]
    assert sum(line.startswith("v ") for line in stdout.splitlines()) == result["model_lines"]
    if result["status"] == "CENSORED_TIME":
        assert statuses in ([], ["s INDETERMINATE"])
        assert result["model_lines"] == 0
        assert any(line.startswith("c rst ") for line in stdout.splitlines())
    elif result["status"] == "CONTROL_GROUP_LIFT_FOUND":
        assert statuses == ["s SATISFIABLE"]
        assert result["producer_xcnf_check"] is not None
        assert load(HERE / "group_lift.json")["status"] == "GROUP_LIFT_FOUND"
    else:
        raise AssertionError("unexpected constructed extraction status")
    receipt = {"status": "PASS_LINEAR_PRODUCT_TERMINAL_AUDIT",
               "query_status": result["status"], "target_q": result["target_q"],
               "target_count": 0, "seed": result["seed"],
               "formula": checked_formula,
               "gate_reductions": {"and_gates": 4118, "cnf_clauses": 12354,
                                   "native_xor_rows": 54, "variables": 4172},
               "construction_plus_search_seconds": result["phase_seconds"]["construction_plus_search"],
               "sampled_peak_combined_rss_bytes": result["sampled_peak_combined_rss_bytes"],
               "sha256": {"auditor": sha(Path(__file__)),
                          "protocol": sha(HERE / "protocol.json"),
                          "control": sha(HERE / "control.json"),
                          "result": sha(HERE / "result.json"),
                          "product_identity": sha(HERE / "product_identity.json"),
                          "formula_gzip": sha(HERE / "system.xcnf.gz")}}
    with (HERE / "terminal_audit.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "query_status": receipt["query_status"],
                      "gate_reductions": receipt["gate_reductions"]}))


if __name__ == "__main__":
    main()
