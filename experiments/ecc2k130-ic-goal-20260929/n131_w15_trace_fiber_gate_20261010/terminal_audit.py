#!/usr/bin/env python3
"""Audit the frozen W15 trace-fiber construction and terminal solver row."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w15_onepair_fixed_sat_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    protocol = load("protocol.json")
    control = load("control_result.json")
    sage = load("sage_trace_audit.json")
    query = load("query_result.json")
    prior_control = json.loads((PRIOR / "fivepair_control_result.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_TRACE_FIBER_CONTROL_AND_QUERY"
    assert protocol["raw_target_reciprocal_traces"] == [0, 1, 0, 1]
    assert protocol["admissible_target_preimage_indices"] == [0, 2]
    assert protocol["eliminated_flag_wires"] == [152, 154]
    assert protocol["constructed_witness_preimage_index"] == 2
    assert protocol["source_sha256"]["runner"] == sha(HERE / "trace_gate.py")
    assert protocol["source_sha256"]["sage_auditor"] == sha(HERE / "sage_trace_audit.py")
    assert protocol["source_sha256"]["runtime"] == sha(HERE / "sage_runtime_info.json")
    assert protocol["source_sha256"]["prior_runner"] == sha(PRIOR / "fivepair_run.py")
    assert protocol["source_sha256"]["prior_circuit"] == sha(PRIOR / "fivepair_circuit.py")
    assert protocol["source_sha256"]["prior_input"] == sha(PRIOR / "fivepair_input.json")
    assert protocol["source_sha256"]["prior_control"] == sha(PRIOR / "fivepair_control_result.json")
    assert protocol["source_sha256"]["prior_group_audit"] == sha(PRIOR / "fivepair_sage_audit.json")
    assert protocol["source_sha256"]["prior_formula_gzip"] == sha(PRIOR / "fivepair_control.xcnf.gz")
    assert protocol["source_sha256"]["solver"] == sha(SOLVER)
    assert prior_control["formula"]["sha256"] == protocol["base_formula_sha256"]
    assert sage["status"] == "PASS_INDEPENDENT_SAGE_TRACE_FIBER_AUDIT"
    assert sage["checked_target_preimages"] == 4
    assert sage["residual_raw_preimage_reciprocal_traces"] == [0, 1, 0, 1]
    for key, path in (("script", HERE / "sage_trace_audit.py"),
                      ("protocol", HERE / "protocol.json"),
                      ("control", HERE / "control_result.json"),
                      ("prior_input", PRIOR / "fivepair_input.json"),
                      ("prior_runner", PRIOR / "fivepair_run.py"),
                      ("runtime", HERE / "sage_runtime_info.json")):
        assert sage["source_sha256"][key] == sha(path)
    assert control["status"] == "PASS_FULL_TRACE_FIBER_XCNF_CONTROL"
    assert control["full_assignment_check"] == {"cnf_clauses": 354230, "xor_rows": 34540}
    assert control["witness_preimage_index"] == 2
    assert control["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert control["source_sha256"]["prior_group_audit"] == sha(PRIOR / "fivepair_sage_audit.json")
    with gzip.open(PRIOR / "fivepair_control.xcnf.gz", "rb") as source:
        base = source.read()
    with gzip.open(HERE / "trace_fiber.xcnf.gz", "rb") as source:
        variant = source.read()
    assert hashlib.sha256(base).hexdigest() == protocol["base_formula_sha256"]
    head, body = base.split(b"\n", 1)
    assert head == b"p cnf 97105 388768"
    first_xor = body.index(b"x")
    assert first_xor > 0 and body[first_xor - 1:first_xor] == b"\n"
    expected = (b"p cnf 97105 388770\n" + body[:first_xor] +
                b"-152 0\n-154 0\n" + body[first_xor:])
    assert variant == expected
    assert hashlib.sha256(variant).hexdigest() == control["formula"]["sha256"]
    assert len(variant) == control["formula"]["bytes"]
    assert control["formula"]["gzip_sha256"] == sha(HERE / "trace_fiber.xcnf.gz")
    assert query["source_sha256"]["formula_gzip"] == sha(HERE / "trace_fiber.xcnf.gz")
    assert query["formula"] == {key: control["formula"][key] for key in
                                 ("sha256", "bytes", "variables", "cnf_clauses", "native_xor_rows")}
    assert query["target_q"] == protocol["target_q"]
    assert query["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert query["source_sha256"]["stdout"] == sha(HERE / "solver.stdout.txt")
    assert query["source_sha256"]["stderr"] == sha(HERE / "solver.stderr.txt")
    assert query["solver_command"][:-1] == [str(SOLVER), *protocol["solver_flags"]]
    assert query["solver_command"][-1] == "/private/tmp/n131_w15_trace_fiber_gate_20261010.xcnf"
    phase = query["phase_seconds"]
    assert abs(phase["build"] + phase["search"] - phase["build_plus_search"]) < .2
    assert phase["build_plus_search"] < protocol["construction_plus_search_cap_seconds"]
    assert query["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    output = (HERE / "solver.stdout.txt").read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    restarts = [line for line in output.splitlines() if line.startswith("c rst ")]
    assert statuses == query["solver_status_lines"]
    assert query["model_lines"] == sum(line.startswith("v ") for line in output.splitlines())
    if query["status"] == "CENSORED_TIME":
        assert query["stop_reason"] == "PARENT_SAFE_STOP"
        assert query["solver_exit_code"] == -15
        assert phase["build_plus_search"] >= protocol["parent_safe_stop_seconds"]
        assert restarts and statuses in ([], ["s INDETERMINATE"])
        assert query["model_lines"] == 0
        assert query["model_check"] is None and query["group_lift_status"] is None
        assert not (HERE / "query_group_lift.json").exists()
    else:
        raise AssertionError("SAT or another terminal status needs independent model audit")
    receipt = {
        "status": "PASS_TRACE_FIBER_TERMINAL_AUDIT",
        "query_status": query["status"],
        "eliminated_fiber_indices": [1, 3],
        "formula_sha256": control["formula"]["sha256"],
        "query_result_sha256": sha(HERE / "query_result.json"),
        "charged_seconds": phase["build_plus_search"],
        "restarts_observed": len(restarts),
        "last_logged_conflicts": restarts[-1].split()[6],
        "audit_source_sha256": sha(__file__),
    }
    with (HERE / "terminal_audit.json").open("x") as sink:
        json.dump(receipt, sink, indent=2, sort_keys=True)
        sink.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
