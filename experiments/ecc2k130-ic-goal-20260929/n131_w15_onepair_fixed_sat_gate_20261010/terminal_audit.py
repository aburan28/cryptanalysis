#!/usr/bin/env python3
"""Audit exact pinned XCNF construction and terminal solver evidence."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
W15 = BASE / "n131_w15_coupled_sixpair_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    source = gzip.open(W15 / "constructed.xcnf.gz", "rb").read()
    pinned = gzip.open(HERE / "pinned.xcnf.gz", "rb").read()
    header, body = source.split(b"\n", 1)
    expected = (b"p cnf 121787 480027\n" + body +
                b"".join(f"{literal} 0\n".encode()
                         for literal in protocol["pin_literals"]))
    assert header == b"p cnf 121787 479997"
    assert pinned == expected
    assert result["formula"]["sha256"] == hashlib.sha256(pinned).hexdigest()
    assert result["formula"]["gzip_sha256"] == sha(HERE / "pinned.xcnf.gz")
    assert result["formula"]["cnf_clauses"] == 436755
    assert result["formula"]["native_xor_rows"] == 43272
    assert protocol["source_sha256"]["constructed_formula_gzip"] == sha(
        W15 / "constructed.xcnf.gz")
    assert result["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["source_sha256"]["stdout"] == sha(HERE / "solver.stdout.txt")
    assert result["source_sha256"]["stderr"] == sha(HERE / "solver.stderr.txt")
    assert result["target_q"] == protocol["target_q"]
    assert result["pinned_masks"] == protocol["pinned_masks"]
    assert result["phase_seconds"]["materialize_plus_search"] < protocol[
        "construction_plus_search_cap_seconds"]
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    lines = (HERE / "solver.stdout.txt").read_text(errors="replace").splitlines()
    restarts = [line for line in lines if line.startswith("c rst ")]
    if result["status"] == "CENSORED_TIME":
        assert restarts and result["model_lines"] == 0
        assert result["solver_status_lines"] in ([], ["s INDETERMINATE"])
    elif result["status"] == "GROUP_LIFT_PENDING_INDEPENDENT_SAGE":
        assert result["solver_status_lines"] == ["s SATISFIABLE"]
        assert result["model_check"] is not None
        assert json.loads((HERE / "group_lift.json").read_text())["status"] == "GROUP_LIFT_FOUND"
    else:
        assert result["status"] in ("OOM", "SAT_NO_GROUP_LIFT",
                                    "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL",
                                    "PRODUCER_OR_SOLVER_FAILURE")
    receipt = {
        "status": "PASS_PINNED_W15_TERMINAL_AUDIT",
        "query_status": result["status"],
        "restarts_observed": len(restarts),
        "last_logged_conflicts": restarts[-1].split()[6] if restarts else None,
        "result_sha256": sha(HERE / "result.json"),
        "formula_sha256": result["formula"]["sha256"],
        "audit_source_sha256": sha(__file__),
    }
    with (HERE / "terminal_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
