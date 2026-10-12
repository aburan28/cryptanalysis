#!/usr/bin/env python3
"""Pair the frozen zero-tau rule against the prior selector on one fixture."""

import hashlib
import json
from pathlib import Path
import random

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from mixed_atlas_screen import make_options
from mixed_radix_scalar import score_fixture


HERE = Path(__file__).resolve().parent


def main():
    path = HERE / "zero-tau-fixture.json"
    raw = path.read_bytes()
    new = json.loads((HERE / "zero-tau-result.json").read_bytes())["panels"][1]
    assert new["fixture_sha256"] == hashlib.sha256(raw).hexdigest()
    tables = [digit_table(seeds) for seeds in SEEDS]
    old = score_fixture(path, tables, make_options(tables, True))
    assert len(old["rows"]) == len(new["rows"]) == 256
    rows = []
    for old_row, new_row in zip(old["rows"], new["rows"]):
        assert old_row["index"] == new_row["index"]
        rows.append({"index": old_row["index"],
                     "previous_M_plus_S": old_row["selected_M_plus_S"],
                     "zero_tau_M_plus_S": new_row["selected_M_plus_S"],
                     "saving_M_plus_S": (old_row["selected_M_plus_S"]
                                         - new_row["selected_M_plus_S"]),
                     "previous_arm": old_row["selected"],
                     "zero_tau_arm": new_row["selected"],
                     "status": new_row["status"]})
    savings = [row["saving_M_plus_S"] for row in rows]
    rng = random.Random(20261007)
    means = sorted(sum(rng.choices(savings, k=len(savings))) / len(savings)
                   for _ in range(5000))
    result = {"schema": 1, "scope": "frozen_new_sage_fixture_source_operations",
              "cases": len(rows), "fixture_sha256": hashlib.sha256(raw).hexdigest(),
              "previous_total": sum(row["previous_M_plus_S"] for row in rows),
              "zero_tau_total": sum(row["zero_tau_M_plus_S"] for row in rows),
              "saving_total": sum(savings),
              "wins": sum(value > 0 for value in savings),
              "ties": sum(value == 0 for value in savings),
              "losses": sum(value < 0 for value in savings),
              "descriptive_bootstrap_mean_95": [means[125], means[4874]],
              "bootstrap_seed": 20261007, "bootstrap_resamples": 5000,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_dependency_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                           for name in ("mixed_radix_scalar.py", "zero_tau_rule.py",
                                                        "selective_mixed_atlas.py")},
              "rows": rows, "cpu_speedup_claim": None}
    target = HERE / "zero-tau-paired-source.json"
    if target.exists():
        raise SystemExit("paired source receipt exists; refusing overwrite")
    target.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("cases", "previous_total", "zero_tau_total", "saving_total",
                       "wins", "ties", "losses", "descriptive_bootstrap_mean_95")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
