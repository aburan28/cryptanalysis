#!/usr/bin/env python3
"""Compare the exact XCNF and observed Gaussian-matrix initialization."""

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "n131_w15_two_fixed_seeds_public_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(folder):
    result = json.loads((folder / "result.json").read_text())
    stdout = (folder / "solver.stdout.txt").read_text(errors="replace")
    assert result["sha256"]["stdout"] == sha(folder / "solver.stdout.txt")
    counts = [int(value) for value in re.findall(
        r"Using (\d+) matrices recovered from", stdout)]
    assert counts
    return result, stdout, counts


def main():
    baseline, old_log, old_counts = read(BASELINE)
    tuned, new_log, new_counts = read(HERE)
    assert baseline["target_q"] == tuned["target_q"]
    assert baseline["formula"] == tuned["formula"]
    # gzip wrappers carry timestamps; the decoded XCNF digest above is the
    # formula identity used for the matched solver comparison.
    assert baseline["status"] == tuned["status"] == "CENSORED_TIME"
    assert baseline["model_lines"] == tuned["model_lines"] == 0
    assert old_counts[0] == 1 and new_counts[0] == 7
    assert all(value == 0 for value in old_counts[1:] + new_counts[1:])
    assert "--maxmatrixcols=4096" in tuned["solver_command"]
    assert "--maxnummatrices=8" in tuned["solver_command"]
    receipt = {
        "status": "PASS_EXACT_FORMULA_MATRIX_POLICY_AUDIT",
        "target_q": tuned["target_q"],
        "formula_sha256": tuned["formula"]["sha256"],
        "matrix_counts_by_init_pass": {"default": old_counts,
                                       "expanded": new_counts},
        "too_many_columns_log_lines": {
            "default": old_log.count("Too many columns in matrix"),
            "expanded": new_log.count("Too many columns in matrix")},
        "query_status": tuned["status"],
        "sha256": {"script": sha(Path(__file__)),
                   "default_result": sha(BASELINE / "result.json"),
                   "expanded_result": sha(HERE / "result.json"),
                   "default_stdout": sha(BASELINE / "solver.stdout.txt"),
                   "expanded_stdout": sha(HERE / "solver.stdout.txt")},
    }
    with (HERE / "matrix_usage_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "initial_matrices": [old_counts[0], new_counts[0]],
                      "later_passes": [len(old_counts)-1, len(new_counts)-1]}))


if __name__ == "__main__":
    main()
