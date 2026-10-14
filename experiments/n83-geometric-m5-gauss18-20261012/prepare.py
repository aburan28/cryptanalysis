#!/usr/bin/env python3
"""Freeze the one-matrix solver pilot on the archived width-18 formula."""

import json
from pathlib import Path

from pilot import HERE, PARENT, ROOT, runner


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    parent_path = PARENT / "protocol.json"
    result_path = PARENT / "width18_ordinary.json"
    parent = json.loads(parent_path.read_text())
    result = json.loads(result_path.read_text())
    assert parent["proposal_id"] == "Q2026101254"
    assert result["proposal_id"] == "Q2026101254"
    formula_path = HERE / "width18.xcnf"
    assert runner.sha(formula_path) == result["attempts"][0][
        "xcnf_raw_sha256"]
    default = Path(parent["solver"]["path"])
    gauss = HERE / "gauss_one.sh"
    sources = {**parent["source_sha256"]}
    for path in (gauss, HERE / "pilot.py", Path(__file__)):
        sources[str(path.relative_to(ROOT))] = runner.sha(path)
    protocol = {
        **parent,
        "kind": "n83_width18_one_gauss_matrix_equal_conflict_protocol",
        "proposal_id": "Q2026101262",
        "comparison_variable": (
            "CryptoMiniSat Gaussian XOR matrix row and column caps "
            "admitting the smallest component; identical archived XCNF"),
        "formula_raw_sha256": runner.sha(formula_path),
        "formula_gzip_sha256": runner.sha(
            PARENT / result["attempts"][0]["xcnf_gzip"]),
        "parent_protocol_sha256": runner.sha(parent_path),
        "parent_result_sha256": runner.sha(result_path),
        "solvers": {"default": {"path": str(default), "sha256": runner.sha(default)},
                    "gauss": {"path": str(gauss), "sha256": runner.sha(gauss),
                              "options": ["--maxmatrixrows", "4096",
                                          "--maxmatrixcols", "4096",
                                          "--maxnummatrices", "1"]}},
        "max_conflicts": 300000,
        "limits": {"wall_seconds_per_arm": 120,
                   "sampled_solver_rss_stop_bytes": 4294967296},
        "run_order": ["default", "gauss", "gauss", "default"],
        "timing_tier": "exploratory_local_unisolated",
        "preflight_stdout_sha256": runner.sha(HERE / "preflight.stdout.txt"),
        "preflight_stderr_sha256": runner.sha(HERE / "preflight.stderr.txt"),
        "source_sha256": sources,
    }
    assert "Using 1 matrices" in (HERE / "preflight.stdout.txt").read_text()
    runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "run_order": protocol["run_order"]}), flush=True)


if __name__ == "__main__":
    main()
