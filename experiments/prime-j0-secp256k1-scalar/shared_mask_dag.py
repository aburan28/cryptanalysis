#!/usr/bin/env python3
"""Share tau-recoding transition arithmetic across all 64 seed masks.

This is an algorithmic screen, not a native timing result. It retains one
per-mask path and its full scoring cost while caching identical ring states.
"""

import json
from pathlib import Path

import hybrid_subset as hybrid


HERE = Path(__file__).resolve().parent
EXTRA_BIT = {seed: bit for bit, seed in enumerate(hybrid.EXTRA_SEEDS)}


class TransitionDAG:
    def __init__(self):
        self.nodes = {}
        self.lookups = 0

    def node(self, a, b):
        self.lookups += 1
        key = a, b
        if key in self.nodes:
            return self.nodes[key]
        if a % 3 == 0:
            assert (a, b) != (0, 0)
            result = None, None, (a + b, -a // 3), None, 0
        else:
            candidate = hybrid.width4.TABLE[(a % 9, b % 9)]
            digit_id = hybrid.WIDTH3_RESIDUES[3 * (a % 9) + b % 3]
            assert digit_id
            unit_index = (digit_id - 1) % 6
            seed_index = hybrid.CORE_SEEDS[(digit_id - 1) // 6]
            da, db = hybrid.WIDTH3_DIGITS[digit_id - 1]
            fallback = (da, db, seed_index, unit_index % 3,
                        -1 if unit_index >= 3 else 1)
            ca, cb = a - candidate[0], b - candidate[1]
            fa, fb = a - fallback[0], b - fallback[1]
            assert ca % 3 == fa % 3 == 0
            bit = 0 if candidate[2] in hybrid.CORE_SEEDS else (
                1 << EXTRA_BIT[candidate[2]])
            result = (candidate, fallback,
                      (ca + cb, -ca // 3), (fa + fb, -fa // 3), bit)
        self.nodes[key] = result
        return result

    def recode(self, a, b, mask):
        assert 0 <= mask < 64
        digits = []
        while a or b:
            if len(digits) >= 256:
                raise ValueError("shared-state tau recoding did not terminate")
            candidate, fallback, yes_next, no_next, bit = self.node(a, b)
            if candidate is None:
                digits.append(None)
                a, b = yes_next
            elif bit == 0 or mask & bit:
                digits.append(candidate)
                a, b = yes_next
            else:
                digits.append(fallback)
                a, b = no_next
        return digits


def main():
    artifact = json.loads((HERE / "adaptive-mask-result.json").read_text())
    assert artifact["verified"] and len(artifact["rows"]) == 64
    total_nodes = total_lookups = 0
    for row in artifact["rows"]:
        a, b = int(row["short_a_hex"], 16), int(row["short_b_hex"], 16)
        graph = TransitionDAG()
        for mask in range(64):
            digits = graph.recode(a, b, mask)
            assert digits == hybrid.recode(a, b, mask)
            assert hybrid.model(digits)["m_plus_s_excluding_inversion"] == (
                row["mask_costs_m_plus_s"][mask])
        total_nodes += len(graph.nodes)
        total_lookups += graph.lookups
    assert total_lookups == artifact["all_recode_positions"]
    print(json.dumps({
        "cases": len(artifact["rows"]), "masks_per_case": 64,
        "digit_positions": total_lookups,
        "unique_ring_states": total_nodes,
        "cached_transition_reuse": total_lookups / total_nodes,
        "all_paths_and_costs_match": True,
        "cpu_speedup_claim": None,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
