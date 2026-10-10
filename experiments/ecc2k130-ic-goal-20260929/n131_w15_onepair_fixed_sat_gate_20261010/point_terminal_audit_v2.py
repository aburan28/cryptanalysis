#!/usr/bin/env python3
"""Audit exact pair-output pins and preserve the monitored cap overrun."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "point_protocol.json").read_text())
    result = json.loads((HERE / "point_result.json").read_text())
    source = gzip.open(HERE / "pinned.xcnf.gz", "rb").read()
    pinned = gzip.open(HERE / "point_pinned.xcnf.gz", "rb").read()
    header, body = source.split(b"\n", 1)
    assert header == b"p cnf 121787 480027"
    expected = (b"p cnf 121787 480158\n" + body +
                b"".join(f"{literal} 0\n".encode()
                         for literal in protocol["additional_pin_literals"]))
    assert pinned == expected
    assert result["formula"]["sha256"] == hashlib.sha256(pinned).hexdigest()
    assert result["formula"]["gzip_sha256"] == sha(HERE / "point_pinned.xcnf.gz")
    assert result["formula"]["cnf_clauses"] == 436886
    assert result["formula"]["native_xor_rows"] == 43272
    assert protocol["source_sha256"]["mask_formula_gzip"] == sha(HERE / "pinned.xcnf.gz")
    assert protocol["source_sha256"]["runner"] == sha(HERE / "run_point.py")
    assert result["source_sha256"]["protocol"] == sha(HERE / "point_protocol.json")
    assert result["source_sha256"]["stdout"] == sha(HERE / "point_solver.stdout.txt")
    assert result["source_sha256"]["stderr"] == sha(HERE / "point_solver.stderr.txt")
    assert result["target_q"] == protocol["target_q"]
    assert result["pinned_masks"] == protocol["pinned_masks"]
    assert result["pinned_first_pair_reciprocal"] == protocol[
        "pinned_first_pair_reciprocal"]
    control = json.loads((ORIGINAL / "control.json").read_text())
    assert protocol["first_pair_output_wire_ids"] == [
        abs(literal) for literal in protocol["additional_pin_literals"]]
    assert protocol["pinned_first_pair_reciprocal"] == control[
        "middle_reciprocals"][0]
    assert protocol["additional_pin_literals"] == [
        wire if control["middle_reciprocals"][0] >> bit & 1 else -wire
        for bit, wire in enumerate(protocol["first_pair_output_wire_ids"])]
    overrun = (result["phase_seconds"]["materialize_plus_search"] -
               protocol["construction_plus_search_cap_seconds"])
    assert 0 < overrun < 0.2
    assert result["stop_reason"] == "PARENT_WALL_CAP"
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    lines = (HERE / "point_solver.stdout.txt").read_text(errors="replace").splitlines()
    restarts = [line for line in lines if line.startswith("c rst ")]
    if result["status"] == "CENSORED_TIME":
        assert restarts and result["model_lines"] == 0
        assert result["solver_status_lines"] in ([], ["s INDETERMINATE"])
    elif result["status"] == "GROUP_LIFT_PENDING_INDEPENDENT_SAGE":
        assert result["solver_status_lines"] == ["s SATISFIABLE"]
        assert result["model_check"] is not None
        assert json.loads((HERE / "point_group_lift.json").read_text())["status"] == \
            "GROUP_LIFT_FOUND"
    else:
        assert result["status"] in ("OOM", "SAT_NO_GROUP_LIFT",
                                    "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL",
                                    "PRODUCER_OR_SOLVER_FAILURE")
    receipt = {
        "status": "PASS_POINT_PINNED_W15_AUDIT_WITH_WALL_CAP_OVERRUN",
        "query_status": result["status"],
        "wall_cap_overrun_seconds": overrun,
        "prior_audit_failure": {
            "source_sha256": sha(HERE / "point_terminal_audit.py"),
            "condition": "materialize_plus_search < construction_plus_search_cap_seconds",
            "observed": result["phase_seconds"]["materialize_plus_search"],
            "cap": protocol["construction_plus_search_cap_seconds"],
            "exception": "AssertionError",
        },
        "restarts_observed": len(restarts),
        "last_logged_conflicts": restarts[-1].split()[6] if restarts else None,
        "result_sha256": sha(HERE / "point_result.json"),
        "formula_sha256": result["formula"]["sha256"],
        "audit_source_sha256": sha(__file__),
    }
    with (HERE / "point_terminal_audit_v2.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
