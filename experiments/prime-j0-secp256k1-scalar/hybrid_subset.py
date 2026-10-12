#!/usr/bin/env python3
"""Fixed-alphabet hybrid width-three/four tau recoder and training screen."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "prime-j0-cost-aware-chain"
sys.path.insert(0, str(OLD))
import run as width4  # noqa: E402
import make_tau3_fused as width3  # noqa: E402


CORE_SEEDS = (0, 1, 3)
EXTRA_SEEDS = (2, 4, 5, 6, 7, 8)
SEED_DEPENDENCIES = {
    0: (), 1: (0,), 2: (1,), 3: (0,), 4: (3,),
    5: (4,), 6: (5,), 7: (3,), 8: (1, 5),
}
SEED_BUILD_M_PLUS_S = {0: 0, 1: 7, 2: 7, 3: 17, 4: 7,
                       5: 11, 6: 7, 7: 11, 8: 16}
WIDTH3_DIGITS, WIDTH3_RESIDUES, *_ = width3.build()


def allowed_seeds(mask):
    assert 0 <= mask < 64
    return set(CORE_SEEDS) | {
        seed for bit, seed in enumerate(EXTRA_SEEDS) if (mask >> bit) & 1
    }


def recode(a, b, mask):
    original = a, b
    allowed = allowed_seeds(mask)
    digits = []
    seen = set()
    while a or b:
        if len(digits) >= 256 or (a, b) in seen:
            raise ValueError("hybrid tau recoding did not terminate")
        seen.add((a, b))
        digit = None
        if a % 3:
            candidate = width4.TABLE[(a % 9, b % 9)]
            if candidate[2] in allowed:
                digit = candidate
            else:
                digit_id = WIDTH3_RESIDUES[3 * (a % 9) + b % 3]
                assert digit_id
                unit_index = (digit_id - 1) % 6
                seed_index = CORE_SEEDS[(digit_id - 1) // 6]
                da, db = WIDTH3_DIGITS[digit_id - 1]
                digit = (da, db, seed_index, unit_index % 3,
                         -1 if unit_index >= 3 else 1)
            a -= digit[0]
            b -= digit[1]
        digits.append(digit)
        assert a % 3 == 0
        a, b = a + b, -a // 3
    assert width4.expand(digits) == original
    return digits


def pair_count(digits):
    if not digits:
        return 0
    assert digits[-1] is not None
    index = len(digits) - 1
    started = False
    pairs = 0
    while index >= 0:
        if started and digits[index] is None and index > 0:
            pairs += 1
            index -= 2
        else:
            started |= digits[index] is not None
            index -= 1
    return pairs


def used_and_closure(digits):
    used = {digit[2] for digit in digits if digit is not None}
    closure = set()

    def add(index):
        if index in closure:
            return
        closure.add(index)
        for required in SEED_DEPENDENCIES[index]:
            add(required)

    for index in used:
        add(index)
    return used, closure


def model(digits):
    if not digits:
        raise ValueError("training model expects a nonzero scalar")
    used, closure = used_and_closure(digits)
    constructed = len(used - {0})
    weight = sum(digit is not None for digit in digits)
    steps = len(digits) - 1
    pairs = pair_count(digits)
    chain = sum(SEED_BUILD_M_PLUS_S[index] for index in closure)
    orbit = len(used)
    normalize = 7 * constructed - 3 if constructed else 0
    online = 6 * steps - 2 * pairs + 11 * (weight - 1)
    return {
        "m_plus_s_excluding_inversion": chain + orbit + normalize + online,
        "inversions": int(constructed > 0),
        "point_chain_m_plus_s": chain,
        "orbit_m": orbit,
        "normalization_m_plus_s": normalize,
        "online_m_plus_s": online,
        "tau_steps": steps,
        "paired_strides": pairs,
        "weight": weight,
        "length": len(digits),
        "used_seed_indices": sorted(used),
        "constructed_seed_indices": sorted(closure - {0}),
    }


def train(output):
    input_path = HERE / "full-prep-result.json"
    training = json.loads(input_path.read_text())
    assert training["verified"] and len(training["rows"]) == 32
    score_rows = []
    for mask in range(64):
        total = 0
        case_costs = []
        for row in training["rows"]:
            a, b = int(row["short_a_hex"], 16), int(row["short_b_hex"], 16)
            score = model(recode(a, b, mask))
            total += score["m_plus_s_excluding_inversion"]
            case_costs.append(score["m_plus_s_excluding_inversion"])
        score_rows.append({"mask": mask, "allowed_seed_indices": sorted(allowed_seeds(mask)),
                           "total_m_plus_s_excluding_inversion": total,
                           "per_case_m_plus_s_excluding_inversion": case_costs})
    best = min(score_rows,
               key=lambda row: (row["total_m_plus_s_excluding_inversion"], row["mask"]))
    result = {
        "schema": 1, "kind": "retrospective-hybrid-subset-training",
        "training_case_count": len(training["rows"]),
        "training_input_sha256": training["input_sha256"],
        "training_artifact_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "score": "single-use generic M+S excluding one inversion and recoding/search",
        "best_mask": best["mask"],
        "best_allowed_seed_indices": best["allowed_seed_indices"],
        "scores": score_rows,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "width3_source_sha256": hashlib.sha256((OLD / "make_tau3_fused.py").read_bytes()).hexdigest(),
        "width4_source_sha256": hashlib.sha256((OLD / "run.py").read_bytes()).hexdigest(),
        "cpu_speedup_claim": None, "academic_novelty_claim": None,
    }
    if output.exists():
        raise SystemExit("training result exists; refusing overwrite")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"best_mask": best["mask"],
                      "best_allowed_seed_indices": best["allowed_seed_indices"],
                      "best_total": best["total_m_plus_s_excluding_inversion"],
                      "width3_total": score_rows[0]["total_m_plus_s_excluding_inversion"],
                      "width4_total": score_rows[63]["total_m_plus_s_excluding_inversion"]},
                     sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    args = parser.parse_args()
    train(args.train)


if __name__ == "__main__":
    main()
