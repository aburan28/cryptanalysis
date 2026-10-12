#!/usr/bin/env python3
"""Fixed three-orbit atlas score on original and freshly frozen inputs."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import BASE_SEEDS, HERE, digit_table, score_case, termination_audit
from seed_chain_bound import double


SEEDS = BASE_SEEDS.copy()
SEEDS[5] = (2, -4)
SEEDS[6] = (4, -8)
SEEDS[7] = (4, 4)
FIXTURES = (HERE / "fixture.json", HERE / "linked-fresh-fixture.json")


def score(path, old_table, new_table):
    raw = path.read_bytes()
    cases = json.loads(raw)["cases"]
    rows = []
    for case in cases:
        baseline = score_case(case, old_table)
        candidate = score_case(case, new_table)
        old = baseline["charged"] + 83
        new = candidate["charged"] + 75
        rows.append({"index": case["index"], "baseline": baseline,
                     "candidate": candidate, "baseline_total": old,
                     "candidate_total": new, "saving": old - new})
    return {"fixture": path.name,
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(rows), "baseline_total": sum(x["baseline_total"] for x in rows),
            "candidate_total": sum(x["candidate_total"] for x in rows),
            "saving": sum(x["saving"] for x in rows),
            "positive_cases": sum(x["saving"] > 0 for x in rows),
            "negative_cases": sum(x["saving"] < 0 for x in rows),
            "tied_cases": sum(x["saving"] == 0 for x in rows),
            "rows": rows}


def main():
    assert SEEDS[5] == double(BASE_SEEDS[8])
    assert SEEDS[6] == double(SEEDS[5])
    assert SEEDS[7] == double(BASE_SEEDS[4])
    old_table = digit_table(BASE_SEEDS)
    new_table = digit_table(SEEDS)
    termination = termination_audit(SEEDS, new_table)
    assert termination["status"] == "terminates"
    panels = [score(path, old_table, new_table) for path in FIXTURES]
    assert panels[0]["cases"] == 64
    assert panels[0]["baseline_total"] == 88656
    assert panels[1]["cases"] == 256
    result = {"schema": 1,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_dependency_sha256": hashlib.sha256(
                  (HERE / "alternate_digit_atlas.py").read_bytes()).hexdigest(),
              "baseline_seeds": BASE_SEEDS, "candidate_seeds": SEEDS,
              "baseline_prep_M_plus_S": 83,
              "candidate_prep_M_plus_S": 75,
              "termination": termination, "panels": panels,
              "cpu_speedup_claim": None, "academic_novelty_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
