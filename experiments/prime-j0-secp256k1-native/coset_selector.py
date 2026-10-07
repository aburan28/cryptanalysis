#!/usr/bin/env python3
"""Choose the best complete source path from three nearby scalar coset representatives."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from mixed_atlas_screen import make_options
from mixed_radix_scalar import source_cost
from screen_coset_representatives import candidates
from screen_radix_policy import recode as radix_recode
from selective_mixed_atlas import recode as selective_recode


HERE = Path(__file__).resolve().parent
FIXTURES = (HERE / "fixture.json", HERE / "coset-fixture.json")
REPRESENTATIVES = 3


def score_fixture(path, tables, options):
    raw = path.read_bytes()
    fixture = json.loads(raw)
    rows = []
    for case in fixture["cases"]:
        scalar = int(case["scalar_hex"], 16)
        representatives = candidates(scalar)[:REPRESENTATIVES]
        assert (representatives[0][2], representatives[0][3]) == (
            int(case["short_a_hex"], 16), int(case["short_b_hex"], 16))
        a0, b0 = representatives[0][2:4]
        digits, selective = selective_recode((a0, b0), tables, options)
        paths = [{"kind": "selective", "norm_rank": 0,
                  "total_M_plus_S": selective["total_M_plus_S"],
                  "digit_sha256": hashlib.sha256(json.dumps(
                      digits, separators=(",", ":")).encode()).hexdigest()}]
        for rank, (n, _, a, b, du, dv) in enumerate(representatives):
            actions, status = radix_recode((a, b), tables[0], "skip_zero_tau")
            assert status == "verified" and actions is not None
            score = source_cost(actions)
            paths.append({"kind": "zero_tau", "norm_rank": rank,
                          "norm": str(n), "a_hex": hex(a), "b_hex": hex(b),
                          "du": du, "dv": dv,
                          "total_M_plus_S": score["total_M_plus_S"],
                          "actions": len(actions),
                          "action_sha256": hashlib.sha256(json.dumps(
                              actions, separators=(",", ":")).encode()).hexdigest(),
                          **score})
        winner_index = min(range(len(paths)), key=lambda index:
                           (paths[index]["total_M_plus_S"], index))
        winner = paths[winner_index]
        old = min(paths[0]["total_M_plus_S"], paths[1]["total_M_plus_S"])
        rows.append({"index": case["index"], "paths": paths,
                     "previous_M_plus_S": old,
                     "selected_M_plus_S": winner["total_M_plus_S"],
                     "saving_M_plus_S": old - winner["total_M_plus_S"],
                     "selected_path_index": winner_index,
                     "selected_kind": winner["kind"],
                     "selected_norm_rank": winner["norm_rank"]})
    return {"fixture": path.name,
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(rows),
            "previous_total": sum(row["previous_M_plus_S"] for row in rows),
            "selected_total": sum(row["selected_M_plus_S"] for row in rows),
            "wins": sum(row["saving_M_plus_S"] > 0 for row in rows),
            "nonshort_choices": sum(row["selected_norm_rank"] > 0 for row in rows),
            "rows": rows}


def main():
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    panels = [score_fixture(path, tables, options) for path in FIXTURES]
    assert [panel["cases"] for panel in panels] == [64, 256]
    assert panels[0]["previous_total"] == 86405
    assert panels[0]["selected_total"] == 85921
    result = {"schema": 1, "representatives": REPRESENTATIVES,
              "ranking": "Eisenstein norm, max absolute coordinate, a, b",
              "selector_ties": "short selective, then zero-tau ranks 0,1,2",
              "panels": panels,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_dependency_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                           for name in ("screen_coset_representatives.py",
                                                        "screen_radix_policy.py", "zero_tau_rule.py",
                                                        "selective_mixed_atlas.py", "alternate_digit_atlas.py")},
              "cpu_speedup_claim": None, "academic_novelty_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
