#!/usr/bin/env python3
"""Audit the frozen exact signed-prefix five-pair control and query receipts."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
W15 = HERE.parent / "n131_w15_coupled_sixpair_20261010"
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
    protocol = load("fivepair_protocol.json")
    control = load("fivepair_control_result.json")
    query = load("fivepair_query_result.json")
    input_record = load("fivepair_input.json")
    lift = load("fivepair_control_group_lift.json")
    sage = load("fivepair_sage_audit.json")
    sources = {
        "runner": HERE / "fivepair_run.py",
        "circuit": HERE / "fivepair_circuit.py",
        "group_lift": HERE / "fivepair_lift.py",
        "input": HERE / "fivepair_input.json",
        "input_preparation": HERE / "prepare_fivepair.py",
        "w15_experiment": W15 / "experiment.py",
        "w15_circuit": W15 / "w15_circuit.py",
        "w15_support": W15 / "support_w15.tsv",
        "w15_group_control": W15 / "control_group_lift.json",
        "runtime": HERE / "sage_runtime_info.json",
        "solver": SOLVER,
    }
    assert protocol["source_sha256"] == {key: sha(path) for key, path in sources.items()}
    assert protocol["status"].startswith("FROZEN_BEFORE_")
    assert protocol["target_q"] == input_record["residual_target_q"] == query["target_q"]
    assert protocol["fixed_first_pair_raw"] == input_record["first_pair_raw"] == query["fixed_first_pair_raw"]
    assert protocol["fixed_first_pair_columns"] == input_record["first_pair_columns"]
    assert protocol["workers"] == 1
    assert protocol["construction_plus_search_cap_seconds"] == 120
    assert protocol["parent_safe_stop_seconds"] == 115
    assert protocol["rss_cap_bytes"] == 4 * 1024**3
    assert control["status"] == "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL"
    assert control["source_sha256"]["protocol"] == sha(HERE / "fivepair_protocol.json")
    assert control["source_sha256"]["group_lift"] == sha(HERE / "fivepair_control_group_lift.json")
    assert lift["status"] == "GROUP_LIFT_FOUND" and lift["solutions"]
    assert control["full_assignment_check"] == {"cnf_clauses": 354228, "xor_rows": 34540}
    assert sage["status"] == "PASS_INDEPENDENT_SAGE_FIVE_PAIR_RESIDUAL_GROUP_REPLAY"
    assert sage["checked_control_solutions"] == len(lift["solutions"])
    for key, name in (("script", "fivepair_sage_audit.py"),
                      ("input", "fivepair_input.json"),
                      ("control_result", "fivepair_control_result.json"),
                      ("control_group_lift", "fivepair_control_group_lift.json"),
                      ("runtime", "sage_runtime_info.json")):
        assert sage["source_sha256"][key] == sha(HERE / name)
    compressed = HERE / "fivepair_control.xcnf.gz"
    assert control["formula"]["gzip_sha256"] == sha(compressed)
    assert query["source_sha256"]["formula_gzip"] == sha(compressed)
    with gzip.open(compressed, "rb") as stream:
        formula = stream.read()
    assert len(formula) == control["formula"]["bytes"] == query["formula"]["bytes"]
    formula_sha = hashlib.sha256(formula).hexdigest()
    assert formula_sha == control["formula"]["sha256"] == query["formula"]["sha256"]
    assert formula.startswith(b"p cnf 97105 388768\n")
    lines = formula.splitlines()
    assert len(lines) - 1 == 388768
    assert sum(line.startswith(b"x") for line in lines[1:]) == 34540
    for receipt in (control, query):
        assert receipt["formula"]["variables"] == 97105
        assert receipt["formula"]["cnf_clauses"] == 354228
        assert receipt["formula"]["native_xor_rows"] == 34540
    assert query["source_sha256"]["protocol"] == sha(HERE / "fivepair_protocol.json")
    assert query["source_sha256"]["stdout"] == sha(HERE / "fivepair_solver.stdout.txt")
    assert query["source_sha256"]["stderr"] == sha(HERE / "fivepair_solver.stderr.txt")
    assert query["solver_command"][:-1] == [str(SOLVER), *protocol["solver_flags"]]
    assert query["solver_command"][-1].endswith("/fivepair.xcnf")
    phase = query["phase_seconds"]
    assert abs(phase["build"] + phase["search"] - phase["build_plus_search"]) < .1
    assert phase["build_plus_search"] < protocol["construction_plus_search_cap_seconds"]
    assert query["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    output = (HERE / "fivepair_solver.stdout.txt").read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    restarts = [line for line in output.splitlines() if line.startswith("c rst ")]
    assert query["solver_status_lines"] == statuses
    assert query["model_lines"] == sum(line.startswith("v ") for line in output.splitlines())
    if query["status"] == "CENSORED_TIME":
        assert query["stop_reason"] == "PARENT_SAFE_STOP"
        assert query["solver_exit_code"] == -15
        assert phase["build_plus_search"] >= protocol["parent_safe_stop_seconds"]
        assert restarts and statuses in ([], ["s INDETERMINATE"])
        assert query["model_lines"] == 0
        assert query["model_check"] is None and query["group_lift_status"] is None
        assert not (HERE / "fivepair_query_group_lift.json").exists()
    else:
        raise AssertionError("unrecognized terminal query status; audit model independently")
    receipt = {
        "status": "PASS_EXACT_SIGNED_PREFIX_FIVE_PAIR_TERMINAL_AUDIT",
        "query_status": query["status"],
        "formula_sha256": formula_sha,
        "query_result_sha256": sha(HERE / "fivepair_query_result.json"),
        "control_group_replay_status": sage["status"],
        "charged_seconds": phase["build_plus_search"],
        "restarts_observed": len(restarts),
        "last_logged_conflicts": restarts[-1].split()[6],
        "audit_source_sha256": sha(__file__),
    }
    with (HERE / "fivepair_terminal_audit.json").open("x") as sink:
        json.dump(receipt, sink, indent=2, sort_keys=True)
        sink.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
