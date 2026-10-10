#!/usr/bin/env python3
"""Exact support ceiling for a blind projected free-four-atom residual."""

import hashlib
import json
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
COUNT = HERE.parent / "n41_upper_xor_projection_20261010/seed_sum_count.json"
getcontext().prec = 60
source = json.loads(COUNT.read_text())["n131"]
pair_states = source["signed_pair_states_per_rotation"]
group_order = int(source["group_order"])
free_fouratom_states_upper = pair_states**2
assert pair_states == 135120112
assert free_fouratom_states_upper == 18257444666892544

record = {
    "status": "EXACT_UNIFORM_SUBGROUP_RESIDUAL_SUPPORT_UPPER",
    "assumption": "residual point sampled uniformly from the order-r subgroup",
    "source_sha256": {
        "uniform_residual_bound.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "seed_sum_count.json": hashlib.sha256(COUNT.read_bytes()).hexdigest()},
    "pair_states_per_rotation": pair_states,
    "free_fouratom_states_upper": free_fouratom_states_upper,
    "subgroup_order": str(group_order),
    "support_probability_upper_numerator": free_fouratom_states_upper,
    "support_probability_upper_denominator": str(group_order),
    "support_probability_upper_decimal": str(
        Decimal(free_fouratom_states_upper) / Decimal(group_order)),
    "inverse_probability_lower_decimal": str(
        Decimal(group_order) / Decimal(free_fouratom_states_upper)),
}
(HERE / "uniform_residual_bound.json").write_text(
    json.dumps(record, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": record["status"],
                  "free_fouratom_states_upper": free_fouratom_states_upper},
                 sort_keys=True))
