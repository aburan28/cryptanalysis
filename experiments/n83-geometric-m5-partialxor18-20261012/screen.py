#!/usr/bin/env python3
"""Compare exact circuit shapes before committing solver time."""

import json
import resource
import time
from pathlib import Path

from partial import HERE, build, flat


def main():
    output = HERE / "shape_screen.json"
    assert not output.exists()
    parent = flat.PARENT
    reference = json.loads((parent / "width18_ordinary.json").read_text())
    onb = flat.runner.field.Onb(83)
    selfcheck = flat.selfcheck(onb)
    rows = []
    for cutoff in (0, 2, 3, 6, 11, 21, 42):
        started = time.perf_counter_ns()
        formula, _, _, _ = build(onb, reference["formula_target_x"], cutoff)
        row = {"cutoff": cutoff, "shape": flat.runner.stats(formula),
               "build_seconds_exploratory": (time.perf_counter_ns() - started) / 1e9,
               "runner_peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        assert row["shape"]["and_gates"] == 12174
        rows.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
    result = {
        "kind": "n83_width18_partial_karatsuba_xor_shape_screen",
        "proposal_id": "Q2026101259", "candidate_id": None,
        "workload_id": "df4396f4d8fc", "target_choice": 0,
        "B": 21714958, "K": 130813,
        "parent_result_sha256": flat.runner.sha(parent / "width18_ordinary.json"),
        "source_sha256": {str(p.relative_to(flat.runner.ROOT)): flat.runner.sha(p)
                          for p in (HERE / "partial.py", HERE / "screen.py")},
        "selfcheck": selfcheck, "rows": rows,
    }
    flat.runner.save(output, result)


if __name__ == "__main__":
    main()
