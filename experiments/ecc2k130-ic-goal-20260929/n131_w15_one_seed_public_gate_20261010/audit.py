#!/usr/bin/env python3
"""Independently compare the pinned public XCNF against the archived base."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_coupled_sixpair_20261010"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text())


def audit_formula(result, control):
    original = load(BASE / "public_query/result.json")["formula"]
    current = result["formula"]
    assert current["variables"] == original["variables"] == 121794
    assert current["clauses"] == original["clauses"] + 30 == 436755
    assert current["xor_rows"] == original["xor_rows"] == 43279
    assert result["pin_clauses"] == control["pin_clauses"]
    assert sha(HERE / "system.xcnf.gz") == result["formula_gzip_sha256"]
    with gzip.open(BASE / "public_query/system.xcnf.gz", "rb") as src, \
         gzip.open(HERE / "system.xcnf.gz", "rb") as dst:
        old_header = next(src)
        new_header = next(dst)
        assert old_header == b"p cnf 121794 480004\n"
        assert new_header == b"p cnf 121794 480034\n"
        digest = hashlib.sha256()
        digest.update(new_header)
        size = len(new_header)
        for _ in range(original["clauses"]):
            left, right = next(src), next(dst)
            assert not left.startswith(b"x") and left == right
            digest.update(right)
            size += len(right)
        for clause in result["pin_clauses"]:
            row = next(dst)
            assert row == (clause + "\n").encode()
            digest.update(row)
            size += len(row)
        for _ in range(original["xor_rows"]):
            left, right = next(src), next(dst)
            assert left.startswith(b"x") and left == right
            digest.update(right)
            size += len(right)
        assert src.read() == dst.read() == b""
    assert digest.hexdigest() == current["sha256"]
    assert size == current["bytes"]
    return {"baseline_formula_sha256": original["sha256"],
            "pinned_formula_sha256": current["sha256"], "bytes": size,
            "unchanged_base_cnf_clauses": original["clauses"],
            "added_seed_clauses": 30, "unchanged_native_xor_rows": original["xor_rows"]}


def main():
    protocol = load(HERE / "protocol.json")
    control = load(HERE / "control.json")
    result = load(HERE / "result.json")
    assert protocol["status"] == "FROZEN_W15_ONE_SEED_PUBLIC_GATE"
    assert control["status"] == "PASS_FIXED_SEED_CONSTRUCTED_WITNESS"
    assert control["protocol_sha256"] == result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["control"] == sha(HERE / "control.json")
    assert result["sha256"]["stdout"] == sha(HERE / "solver.stdout.txt")
    assert result["sha256"]["stderr"] == sha(HERE / "solver.stderr.txt")
    assert result["sha256"]["formula_gzip"] == sha(HERE / "system.xcnf.gz")
    assert result["target_q"] == protocol["target_q"]
    assert result["seed"] == protocol["support"]["seed"] == 13686
    assert result["phase_seconds"]["construction_plus_search"] <= protocol["construction_plus_search_cap_seconds"]
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    counts = {int(a): int(b) for a, b in
              (line.split() for line in
               (HERE.parent / "n131_w15_cross_block_seed_offset_20261010/signed_seed_counts.tsv").read_text().splitlines())}
    assert counts[13686] == protocol["support"]["signed_pair_states_for_seed"] == 16576
    assert sum(counts.values()) == protocol["support"]["signed_pair_states_total"] == 540579832
    assert sum(x*x for x in counts.values()) == protocol["support"]["same_seed_block_states_total"] == 8918874017088
    formula = audit_formula(result, control)
    stdout = (HERE / "solver.stdout.txt").read_text(errors="replace")
    statuses = [line for line in stdout.splitlines() if line.startswith("s ")]
    assert statuses == result["solver_status_lines"]
    assert sum(line.startswith("v ") for line in stdout.splitlines()) == result["model_lines"]
    if result["status"] == "CENSORED_TIME":
        assert statuses in ([], ["s INDETERMINATE"])
        assert result["model_lines"] == 0
        assert any(line.startswith("c rst ") for line in stdout.splitlines())
    elif result["status"] == "GROUP_RELATION_PENDING_INDEPENDENT_SAGE":
        assert statuses == ["s SATISFIABLE"]
        assert result["producer_xcnf_check"] is not None
        assert load(HERE / "group_lift.json")["status"] == "GROUP_LIFT_FOUND"
    elif result["status"] == "UNSAT_FORMULA":
        assert statuses == ["s UNSATISFIABLE"]
    elif result["status"] == "OOM":
        assert result["stop_reason"] == "RSS_CAP"
    else:
        raise AssertionError("uncertified terminal status")
    receipt = {"status": "PASS_ONE_SEED_FORMULA_AND_TERMINAL_AUDIT",
               "query_status": result["status"], "curve_id": protocol["curve_id"],
               "target_q": protocol["target_q"], "seed": 13686,
               "support": protocol["support"], "formula": formula,
               "construction_plus_search_seconds": result["phase_seconds"]["construction_plus_search"],
               "peak_rss_bytes": result["sampled_peak_combined_rss_bytes"],
               "sha256": {"auditor": sha(Path(__file__)),
                          "protocol": sha(HERE / "protocol.json"),
                          "control": sha(HERE / "control.json"),
                          "result": sha(HERE / "result.json"),
                          "stdout": sha(HERE / "solver.stdout.txt"),
                          "stderr": sha(HERE / "solver.stderr.txt"),
                          "formula_gzip": sha(HERE / "system.xcnf.gz")}}
    with (HERE / "terminal_audit.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "query_status": receipt["query_status"],
                      "formula": formula}))


if __name__ == "__main__":
    main()
