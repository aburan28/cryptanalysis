#!/usr/bin/env python3
"""Compare middle-trace propagation against the eight-seed public XCNF."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_seed8_trace_public_gate_20261010"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text())


def audit_formula(result, control):
    original = load(BASE / "result.json")["formula"]
    current = result["formula"]
    assert current["variables"] == original["variables"] == 121794
    assert current["clauses"] == original["clauses"] + 20 == 436771
    assert current["xor_rows"] == original["xor_rows"] == 43279
    assert result["pin_clauses"] == control["pin_clauses"]
    assert sha(HERE / "system.xcnf.gz") == result["formula_gzip_sha256"]
    with gzip.open(BASE / "system.xcnf.gz", "rb") as src, \
         gzip.open(HERE / "system.xcnf.gz", "rb") as dst:
        old_header = next(src)
        new_header = next(dst)
        assert old_header == b"p cnf 121794 480030\n"
        assert new_header == b"p cnf 121794 480050\n"
        digest = hashlib.sha256()
        digest.update(new_header)
        size = len(new_header)
        for _ in range(original["clauses"]):
            left, right = next(src), next(dst)
            assert not left.startswith(b"x") and left == right
            digest.update(right)
            size += len(right)
        assert result["pin_clauses"][:26] == load(BASE / "result.json")["pin_clauses"]
        for clause in result["pin_clauses"][26:]:
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
            "added_middle_trace_clauses": 20,
            "unchanged_native_xor_rows": original["xor_rows"]}


def main():
    protocol = load(HERE / "protocol.json")
    control = load(HERE / "control.json")
    result = load(HERE / "result.json")
    assert protocol["status"] == "FROZEN_W15_SEED8_MIDDLETRACE_PUBLIC_GATE"
    assert control["status"] == "PASS_SEED8_MIDDLETRACE_CONSTRUCTED_WITNESS"
    assert control["protocol_sha256"] == result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["control"] == sha(HERE / "control.json")
    assert result["sha256"]["stdout"] == sha(HERE / "solver.stdout.txt")
    assert result["sha256"]["stderr"] == sha(HERE / "solver.stderr.txt")
    assert result["sha256"]["formula_gzip"] == sha(HERE / "system.xcnf.gz")
    assert result["target_q"] == protocol["target_q"]
    assert result["seed_family"] == protocol["support"]["seed_family"] == list(range(13680, 13688))
    assert result["admissible_target_preimage_indices"] == [0, 2]
    assert result["middle_trace_parity_bit_indices"] == [0, 129]
    proof = load(HERE / "trace_proof.json")
    assert proof["status"] == "PASS_EXACT_N131_TRACE_PARITY_AND_CONSTRUCTED_MIDDLES"
    assert proof["polynomial_basis_trace_support"] == [0, 129]
    trace = load(HERE.parent / "n131_w15_one_seed_public_gate_20261010/trace_result.json")
    assert trace["status"] == "PASS_PUBLIC_RECIPROCAL_TRACE_FIBER"
    assert trace["target_q"] == result["target_q"]
    assert trace["admissible_target_preimage_indices"] == [0, 2]
    assert result["phase_seconds"]["construction_plus_search"] <= protocol["construction_plus_search_cap_seconds"]
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    counts = {int(a): int(b) for a, b in
              (line.split() for line in
               (HERE.parent / "n131_w15_cross_block_seed_offset_20261010/signed_seed_counts.tsv").read_text().splitlines())}
    assert counts[13686] == protocol["support"]["signed_pair_states_for_control_seed"] == 16576
    assert sum(counts.values()) == protocol["support"]["signed_pair_states_total"] == 540579832
    assert sum(x*x for x in counts.values()) == protocol["support"]["same_seed_block_states_total"] == 8918874017088
    assert sum(counts[seed]**2 for seed in result["seed_family"]) == protocol["support"]["seed_family_block_states"] == 2181396304
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
    receipt = {"status": "PASS_MIDDLE_TRACE_FORMULA_AND_TERMINAL_AUDIT",
               "query_status": result["status"], "curve_id": protocol["curve_id"],
               "target_q": protocol["target_q"], "seed_family": result["seed_family"],
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
