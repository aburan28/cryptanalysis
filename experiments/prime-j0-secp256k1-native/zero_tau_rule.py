#!/usr/bin/env python3
"""Fixed zero-tau priority recoder with complete selective-path comparison."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from mixed_atlas_screen import make_options
from mixed_radix_scalar import source_cost
from screen_radix_policy import recode, termination_audit
from selective_mixed_atlas import recode as selective_recode


HERE = Path(__file__).resolve().parent
FIXTURES = (HERE / "fixture.json", HERE / "zero-tau-fixture.json")
POLICY = "skip_zero_tau"


def score_fixture(path, tables, options):
    raw = path.read_bytes()
    fixture = json.loads(raw)
    rows = []
    for case in fixture["cases"]:
        short = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
        actions, status = recode(short, tables[0], POLICY)
        digits, selective = selective_recode(short, tables, options)
        if actions is None:
            rows.append({"index": case["index"], "status": status,
                         "policy_M_plus_S": None,
                         "selective_M_plus_S": selective["total_M_plus_S"],
                         "selected_M_plus_S": selective["total_M_plus_S"],
                         "selected": "selective"})
            continue
        policy_cost = source_cost(actions)
        choose_policy = policy_cost["total_M_plus_S"] < selective["total_M_plus_S"]
        rows.append({"index": case["index"], "status": status,
                     "policy_M_plus_S": policy_cost["total_M_plus_S"],
                     "selective_M_plus_S": selective["total_M_plus_S"],
                     "selected_M_plus_S": min(policy_cost["total_M_plus_S"],
                                              selective["total_M_plus_S"]),
                     "selected": "zero_tau" if choose_policy else "selective",
                     "actions": len(actions),
                     "action_sha256": hashlib.sha256(json.dumps(
                         actions, separators=(",", ":")).encode()).hexdigest(),
                     "selective_digit_sha256": hashlib.sha256(json.dumps(
                         digits, separators=(",", ":")).encode()).hexdigest(),
                     **policy_cost})
    return {"fixture": path.name, "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(rows), "policy_total": sum(row["policy_M_plus_S"]
                                                   for row in rows if row["policy_M_plus_S"] is not None),
            "selective_total": sum(row["selective_M_plus_S"] for row in rows),
            "selected_total": sum(row["selected_M_plus_S"] for row in rows),
            "zero_tau_choices": sum(row["selected"] == "zero_tau" for row in rows),
            "failures": sum(row["status"] != "verified" for row in rows),
            "rows": rows}


def main():
    tables = [digit_table(seeds) for seeds in SEEDS]
    audit = termination_audit(tables[0], POLICY)
    assert audit["status"] == "terminates"
    options = make_options(tables, True)
    panels = [score_fixture(path, tables, options) for path in FIXTURES]
    assert [panel["cases"] for panel in panels] == [64, 256]
    assert panels[0]["selected_total"] == 86405
    result = {"schema": 1, "policy": POLICY,
              "small_norm_termination": audit,
              "panels": panels,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_dependency_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                           for name in ("screen_radix_policy.py", "mixed_radix_scalar.py",
                                                        "selective_mixed_atlas.py", "alternate_digit_atlas.py",
                                                        "mixed_atlas_screen.py", "atlas_portfolio.py")},
              "cpu_speedup_claim": None, "academic_novelty_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
