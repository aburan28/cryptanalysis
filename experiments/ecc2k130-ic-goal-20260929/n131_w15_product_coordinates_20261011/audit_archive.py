#!/usr/bin/env python3
"""Read-only checks on the frozen product-coordinate public gate."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
OLD = PARENT / "n131_w15_two_fixed_seeds_public_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_formula(path, expected):
    digest = hashlib.sha256()
    clauses = xors = 0
    header = None
    with gzip.open(path, "rb") as stream:
        for line in stream:
            digest.update(line)
            if line.startswith(b"p cnf "):
                header = tuple(map(int, line.split()[2:]))
            elif line.startswith(b"x "):
                xors += 1
            elif line.strip():
                clauses += 1
    assert header == (expected["variables"], clauses+xors)
    assert clauses == expected["clauses"]
    assert xors == expected["xor_rows"]
    assert digest.hexdigest() == expected["raw_sha256"]
    assert sha(path) == expected["gzip_sha256"]
    return {"header": header, "clauses": clauses, "xor_rows": xors,
            "raw_sha256": digest.hexdigest(), "gzip_sha256": sha(path)}


def main():
    protocol = json.loads((HERE / "public_protocol.json").read_text())
    result = json.loads((HERE / "public_result.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    preflight = json.loads((HERE / "result.json").read_text())
    previous = json.loads((OLD / "result.json").read_text())
    assert protocol["status"] == "FROZEN_PRODUCT_COORDINATE_PUBLIC_QUERY"
    assert preflight["status"] == "PASS_EXACT_PRODUCT_COORDINATE_SOURCE_BIJECTION"
    assert control["status"] == "PASS_PRODUCT_COORDINATE_COMPLETE_CONSTRUCTED_CONTROL"
    assert control["xcnf_check"] == {"cnf_clauses": 363985, "xor_rows": 42681}
    assert control["group_lift"]["status"] == "GROUP_LIFT_FOUND"
    assert result["target_q"] == protocol["target_q"] == previous["target_q"]
    assert result["source_sha256"] == protocol["source_sha256"]
    assert result["construction_plus_search_seconds"] <= 601
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"] \
        or result["status"] == "CENSORED_RSS"
    control_formula = check_formula(HERE / "control.xcnf.gz", control["formula"])
    public_formula = check_formula(HERE / "system.xcnf.gz", result["formula"])
    stdout = (HERE / "solver.stdout.txt").read_text(errors="replace")
    stderr = (HERE / "solver.stderr.txt").read_text(errors="replace")
    assert sha(HERE / "solver.stdout.txt") == result["solver_stdout_sha256"]
    assert sha(HERE / "solver.stderr.txt") == result["solver_stderr_sha256"]
    statuses = [line for line in stdout.splitlines() if line.startswith("s ")]
    models = [line for line in stdout.splitlines() if line.startswith("v ")]
    assert statuses == result["solver_status_lines"]
    assert len(models) == result["model_line_count"]
    if result["status"] in ("CENSORED_TIME", "CENSORED_RSS"):
        assert not models and not any("SATISFIABLE" in line for line in statuses)
        assert "c " in stdout
    elif result["status"] == "MODEL_REQUIRES_INDEPENDENT_REPLAY":
        assert models and "s SATISFIABLE" in statuses
    else:
        raise AssertionError(f"unexpected terminal status {result['status']}")
    rows = preflight["cases"]
    assert [(r["seed_code"], r["product_rank"], r["valid_unordered_pairs"],
             r["bdd_nodes"]) for r in rows] == [
                 (12004, 14, 4088, 2065), (9022, 14, 4170, 2083)]
    audit = {"status": "PASS_PRODUCT_COORDINATE_ARCHIVE_BINDINGS",
             "result_status": result["status"], "target_q": result["target_q"],
             "control_formula": control_formula, "public_formula": public_formula,
             "solver_status_lines": statuses, "model_line_count": len(models),
             "source_result_sha256": sha(HERE / "result.json"),
             "control_result_sha256": sha(HERE / "control_result.json"),
             "public_result_sha256": sha(HERE / "public_result.json"),
             "audit_source_sha256": sha(Path(__file__))}
    with (HERE / "audit_result.json").open("x") as out:
        json.dump(audit, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": audit["status"],
                      "result_status": audit["result_status"],
                      "public_formula": public_formula}))


if __name__ == "__main__":
    main()
