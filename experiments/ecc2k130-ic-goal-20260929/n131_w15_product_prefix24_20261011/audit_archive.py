#!/usr/bin/env python3
"""Read-only archive checks for the exact W15 prefix-support public gate."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PREVIOUS = PARENT / "n131_w15_product_coordinates_20261011"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def formula(path, expected):
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
    return {"variables": header[0], "clauses": clauses,
            "xor_rows": xors, "raw_sha256": digest.hexdigest()}


def main():
    protocol = json.loads((HERE / "run_protocol.json").read_text())
    projection = json.loads((HERE / "projection.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    public = json.loads((HERE / "public_result.json").read_text())
    prior_control = json.loads((PREVIOUS / "control_result.json").read_text())
    prior_public = json.loads((PREVIOUS / "public_result.json").read_text())
    assert protocol["status"] == "FROZEN_N131_W15_PREFIX24_PUBLIC_GATE"
    assert projection["status"] == "PASS_EXACT_W15_PREFIX24_PROJECTION"
    assert control["status"] == "PASS_PREFIX24_COMPLETE_CONSTRUCTED_CONTROL"
    assert control["xcnf_check"] == {"cnf_clauses": 430526, "xor_rows": 42681}
    assert control["group_lift"]["status"] == "GROUP_LIFT_FOUND"
    assert public["target_q"] == prior_public["target_q"] == protocol["target_q"]
    assert public["source_sha256"] == control["source_sha256"] == protocol["source_sha256"]
    assert [row["forward_clauses"] for row in projection["rows"]] == [33084, 33457]
    for present, previous in ((control, prior_control), (public, prior_public)):
        now = present["formula"]
        old = previous["formula"]
        assert now["clauses"] - old["clauses"] == 66541
        assert now["variables"] - old["variables"] == 33273
        assert now["xor_rows"] == old["xor_rows"]
        assert now["and_gates"] == old["and_gates"] == 72641
    control_form = formula(HERE / "control.xcnf.gz", control["formula"])
    public_form = formula(HERE / "system.xcnf.gz", public["formula"])
    assert public["construction_plus_search_seconds"] <= 601
    assert public["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"] \
        or public["status"] == "CENSORED_RSS"
    stdout = (HERE / "solver.stdout.txt").read_text(errors="replace")
    statuses = [line for line in stdout.splitlines() if line.startswith("s ")]
    models = [line for line in stdout.splitlines() if line.startswith("v ")]
    assert statuses == public["solver_status_lines"]
    assert len(models) == public["model_line_count"]
    assert sha(HERE / "solver.stdout.txt") == public["solver_stdout_sha256"]
    assert sha(HERE / "solver.stderr.txt") == public["solver_stderr_sha256"]
    if public["status"] in ("CENSORED_TIME", "CENSORED_RSS"):
        assert not statuses and not models and "c " in stdout
    elif public["status"] == "MODEL_REQUIRES_INDEPENDENT_REPLAY":
        assert "s SATISFIABLE" in statuses and models
    else:
        raise AssertionError(f"unexpected terminal status {public['status']}")
    result = {"status": "PASS_PREFIX24_ARCHIVE_BINDINGS",
              "public_status": public["status"], "target_q": public["target_q"],
              "control_formula": control_form, "public_formula": public_form,
              "solver_status_lines": statuses, "model_line_count": len(models),
              "source_sha256": sha(Path(__file__)),
              "control_result_sha256": sha(HERE / "control_result.json"),
              "public_result_sha256": sha(HERE / "public_result.json")}
    with (HERE / "audit_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "public_status": result["public_status"],
                      "public_formula": public_form}))


if __name__ == "__main__":
    main()
