#!/usr/bin/env python3
"""Fixed two-orbit τ atlas candidate, including one-use seed preparation."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import (BASE_SEEDS, HERE, digit_table,
                                   score_case, termination_audit)
from seed_chain_bound import add, double, orbit


FIXTURES = (HERE / "fixture.json", HERE / "fresh-fixture.json")
ALTERNATE = BASE_SEEDS.copy()
ALTERNATE[5] = (2, -4)
ALTERNATE[6] = (4, -8)
BASE_PREP = 83
ALTERNATE_PREP = 79


def audit_single_slot_preparation():
    raw = (HERE / "alternate-digit-atlas-result.json").read_bytes()
    result = json.loads(raw)
    positive = [row for row in result["rows"] if
                row["charged_saving_before_unknown_seed_prep"] is not None
                and row["charged_saving_before_unknown_seed_prep"] > 0]
    assert len(positive) == 31
    special = []
    for row in positive:
        slot = row["slot"]
        candidate = tuple(row["candidate"])
        other = [seed for index, seed in enumerate(BASE_SEEDS)
                 if index != slot]
        doubles = [source for source in other if
                   candidate in orbit(double(source))]
        if doubles:
            assert slot == 5 and candidate == (-10, 6)
            special.append(row)
        else:
            assert row["charged_saving_before_unknown_seed_prep"] < 3 * 64
    assert len(special) == 1
    assert special[0]["charged_saving_before_unknown_seed_prep"] == 153
    # With only slot 5 changed, unchanged slot 6 can be made as 4P minus
    # the new slot 5. Both inputs are projective in the existing setup.
    available = [seed for index, seed in enumerate(BASE_SEEDS)
                 if index not in (5, 6)] + [(-10, 6)]
    direct_pairs = []
    for first in available:
        for second in available:
            for u in orbit(first):
                for v in orbit(second):
                    if add(u, v) in orbit(BASE_SEEDS[6]):
                        direct_pairs.append((first, second, u, v))
    assert direct_pairs
    assert all({first, second} == {(4, 0), (-10, 6)}
               for first, second, _, _ in direct_pairs)
    return {"one_slot_source_sha256": hashlib.sha256(raw).hexdigest(),
            "positive_one_slot_candidates": len(positive),
            "special_candidate": special[0]["candidate"],
            "special_evaluator_saving": 153,
            "other_max_evaluator_saving": max(
                row["charged_saving_before_unknown_seed_prep"]
                for row in positive if row is not special[0]),
            "slot6_direct_pair_count_after_special_replacement": len(direct_pairs),
            "slot6_direct_pair_sources": [[4, 0], [-10, 6]]}


def score_fixture(path, old_table, new_table):
    raw = path.read_bytes()
    cases = json.loads(raw)["cases"]
    rows = []
    for case in cases:
        baseline = score_case(case, old_table)
        candidate = score_case(case, new_table)
        baseline_total = baseline["charged"] + BASE_PREP
        candidate_total = candidate["charged"] + ALTERNATE_PREP
        rows.append({"index": case["index"], "baseline": baseline,
                     "candidate": candidate,
                     "baseline_total": baseline_total,
                     "candidate_total": candidate_total,
                     "saving": baseline_total - candidate_total})
    return {"fixture": path.name,
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(rows), "baseline_total": sum(r["baseline_total"] for r in rows),
            "candidate_total": sum(r["candidate_total"] for r in rows),
            "saving": sum(r["saving"] for r in rows),
            "positive_cases": sum(r["saving"] > 0 for r in rows),
            "negative_cases": sum(r["saving"] < 0 for r in rows),
            "tied_cases": sum(r["saving"] == 0 for r in rows),
            "min_saving": min(r["saving"] for r in rows),
            "max_saving": max(r["saving"] for r in rows),
            "rows": rows}


def main():
    assert ALTERNATE[5] == double(BASE_SEEDS[8])
    assert ALTERNATE[6] == double(ALTERNATE[5])
    assert orbit(ALTERNATE[5]) != orbit(BASE_SEEDS[5])
    assert orbit(ALTERNATE[6]) != orbit(BASE_SEEDS[6])
    old_table = digit_table(BASE_SEEDS)
    new_table = digit_table(ALTERNATE)
    one_slot_audit = audit_single_slot_preparation()
    audit = termination_audit(ALTERNATE, new_table)
    assert audit["status"] == "terminates"
    panels = [score_fixture(path, old_table, new_table) for path in FIXTURES]
    assert panels[0]["cases"] == 64
    assert panels[0]["baseline_total"] == 88656
    assert panels[1]["cases"] == 256
    result = {"schema": 1,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_dependency_sha256": hashlib.sha256(
                  (HERE / "alternate_digit_atlas.py").read_bytes()).hexdigest(),
              "base_seeds": BASE_SEEDS, "candidate_seeds": ALTERNATE,
              "base_prep_M_plus_S": BASE_PREP,
              "candidate_prep_M_plus_S": ALTERNATE_PREP,
              "termination": audit, "panels": panels,
              "one_slot_preparation_audit": one_slot_audit,
              "cost_boundary": "source-count M+S, one-use seed/orbit prep plus tau/add/cache evaluator; excludes lattice reduction, final inversion, and CPU timing",
              "cpu_speedup_claim": None, "academic_novelty_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
