#!/usr/bin/env python3
"""Audit the frozen unrestricted five-pair public formula and terminal row."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text())


def formula(path, form, added):
    digest = hashlib.sha256()
    size = clauses = xors = 0
    tail = []
    with gzip.open(path, "rb") as stream:
        header = next(stream)
        assert header == f"p cnf {form['variables']} {form['clauses']+form['xor_rows']}\n".encode()
        digest.update(header)
        size += len(header)
        for line in stream:
            digest.update(line)
            size += len(line)
            if line.startswith(b"x"):
                xors += 1
            else:
                clauses += 1
                tail.append(line.decode().strip())
                if len(tail) > len(added):
                    tail.pop(0)
    assert digest.hexdigest() == form["sha256"]
    assert size == form["bytes"]
    assert clauses == form["clauses"] and xors == form["xor_rows"]
    assert tail == added
    return {"sha256": digest.hexdigest(), "bytes": size,
            "variables": form["variables"], "cnf_clauses": clauses,
            "native_xor_rows": xors, "verified_appended_trace_clauses": len(added)}


def main():
    protocol = load(HERE / "protocol.json")
    control = load(HERE / "control.json")
    inp = load(HERE / "input.json")
    sage = load(HERE / "prefix_sage_audit.json")
    result = load(HERE / "result.json")
    assert protocol["status"] == "FROZEN_UNRESTRICTED_W15_FIVEPAIR_PUBLIC_GATE_V2"
    assert control["status"] == "PASS_UNRESTRICTED_FIVEPAIR_CONSTRUCTED_CONTROL"
    assert sage["status"] == "PASS_INDEPENDENT_SAGE_PREFIX_AND_RESIDUALS"
    assert inp["status"] == "PASS_TARGET_INDEPENDENT_PREFIX_AND_RESIDUALS"
    assert protocol["target_count"] == result["target_count"] == 1
    assert protocol["target_q"] == result["target_q"] == inp["public_target_q"]
    assert result["prefix_masks"] == protocol["prefix_masks"] == inp["prefix_masks"] == [4, 17]
    assert result["prefix_columns"] == protocol["prefix_columns"] == [4, 17]
    assert result["residual_q"] == protocol["public_residual_target_q"] == inp["public_residual_target_q"]
    assert control["xcnf_check"] == {"cnf_clauses": 354246, "xor_rows": 34510}
    assert control["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["formula"]["variables"] == 97075
    assert result["formula"]["variables"] == 97074
    assert control["formula"]["clauses"] == result["formula"]["clauses"] == 354246
    assert control["formula"]["xor_rows"] == 34510
    assert result["formula"]["xor_rows"] == 34509
    assert result["added_trace_clauses"] == control["added_trace_clauses"]
    assert len(result["added_trace_clauses"]) == 18
    assert control["protocol_sha256"] == result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    for key, file in (("control", "control.json"), ("stdout", "solver.stdout.txt"),
                      ("stderr", "solver.stderr.txt"), ("formula_gzip", "system.xcnf.gz")):
        assert result["sha256"][key] == sha(HERE / file)
    assert result["formula_gzip_sha256"] == sha(HERE / "system.xcnf.gz")
    assert protocol["sources_sha256"]["runner"] == sha(HERE / "run.py")
    assert protocol["sources_sha256"]["circuit"] == sha(HERE / "circuit.py")
    assert protocol["sources_sha256"]["group_lift"] == sha(HERE / "lift.py")
    assert protocol["sources_sha256"]["input"] == sha(HERE / "input.json")
    assert result["phase_seconds"]["construction_plus_search"] <= protocol["construction_plus_search_cap_seconds"]
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    checked_form = formula(HERE / "system.xcnf.gz", result["formula"],
                           result["added_trace_clauses"])
    stdout = (HERE / "solver.stdout.txt").read_text(errors="replace")
    statuses = [line for line in stdout.splitlines() if line.startswith("s ")]
    models = sum(line.startswith("v ") for line in stdout.splitlines())
    assert statuses == result["solver_status_lines"] and models == result["model_lines"]
    if result["status"] == "CENSORED_TIME":
        assert statuses in ([], ["s INDETERMINATE"])
        assert models == 0
        assert any(line.startswith("c rst ") for line in stdout.splitlines())
    elif result["status"] == "GROUP_RELATION_PENDING_INDEPENDENT_SAGE":
        assert statuses == ["s SATISFIABLE"] and models > 0
        assert result["producer_xcnf_check"] is not None
        assert load(HERE / "group_lift.json")["status"] == "GROUP_LIFT_FOUND"
    elif result["status"] == "UNSAT_FORMULA":
        assert statuses == ["s UNSATISFIABLE"]
    elif result["status"] == "OOM":
        assert result["stop_reason"] == "RSS_CAP"
    else:
        raise AssertionError("uncertified terminal status")
    receipt = {"status": "PASS_UNRESTRICTED_FIVEPAIR_TERMINAL_AUDIT",
               "query_status": result["status"], "curve_id": protocol["curve_id"],
               "target_q": result["target_q"], "residual_q": result["residual_q"],
               "prefix_masks": result["prefix_masks"], "support": protocol["support"],
               "formula": checked_form,
               "construction_plus_search_seconds": result["phase_seconds"]["construction_plus_search"],
               "sampled_peak_combined_rss_bytes": result["sampled_peak_combined_rss_bytes"],
               "sha256": {"auditor": sha(Path(__file__)),
                          "protocol": sha(HERE / "protocol.json"),
                          "control": sha(HERE / "control.json"),
                          "result": sha(HERE / "result.json"),
                          "sage_prefix_audit": sha(HERE / "prefix_sage_audit.json"),
                          "formula_gzip": sha(HERE / "system.xcnf.gz"),
                          "stdout": sha(HERE / "solver.stdout.txt"),
                          "stderr": sha(HERE / "solver.stderr.txt")}}
    with (HERE / "terminal_audit.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "query_status": receipt["query_status"],
                      "formula": checked_form}))


if __name__ == "__main__":
    main()
