#!/usr/bin/env python3
"""Bounded search over position-wise width-three/four tau digit choices.

Unlike a six-bit global seed mask, each nonzero position may choose the
width-four residue digit or its width-three fallback. Search scores the
complete single-use prepared-point cost and always retains width four as a
fallback. This is public-scalar experimental code, not constant-time code.
"""

import argparse
import hashlib
import json
from pathlib import Path

import hybrid_subset as hybrid
from shared_mask_dag import TransitionDAG


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-position-adaptive-training-20261007-v1"
BEAM_WIDTH = 64
MAX_POSITIONS = 256


def norm(a, b):
    return a * a + 3 * a * b + 3 * b * b


def prepared_cost(used_bits):
    used = {index for index in range(9) if used_bits & (1 << index)}
    if not used:
        return 0
    closure = set()

    def add(index):
        if index in closure:
            return
        closure.add(index)
        for parent in hybrid.SEED_DEPENDENCIES[index]:
            add(parent)

    for index in used:
        add(index)
    constructed = len(used - {0})
    chain = sum(hybrid.SEED_BUILD_M_PLUS_S[index] for index in closure)
    orbit = len(used)
    normalize = 7 * constructed - 3 if constructed else 0
    return chain + orbit + normalize


PREP_COST = tuple(prepared_cost(bits) for bits in range(1 << 9))


def rank(state):
    a, b, used_bits, digits, weight = state
    remaining = (norm(a, b).bit_length() * 63) // 100 if (a or b) else 0
    # About 7.4 field units per still-unknown tau position. This is only a
    # beam ordering heuristic; the final winner uses hybrid.model exactly.
    return (PREP_COST[used_bits] + 6 * len(digits) + 11 * weight +
            7 * remaining + (2 * remaining) // 5,
            norm(a, b), used_bits)


def search(a, b, width=BEAM_WIDTH):
    if not a and not b:
        return [], {"expanded_states": 0, "completed_paths": 1,
                    "beam_width": width}
    original = a, b
    graph = TransitionDAG()
    frontier = [(a, b, 0, (), 0)]
    best = None
    best_score = None
    expanded = completed = 0
    for _position in range(MAX_POSITIONS):
        next_states = []
        for state in frontier:
            x, y, used_bits, digits, weight = state
            candidate, fallback, yes_next, no_next, _bit = graph.node(x, y)
            expanded += 1
            choices = ((None, yes_next),) if candidate is None else (
                ((candidate, yes_next),) if candidate == fallback else
                ((candidate, yes_next), (fallback, no_next)))
            for digit, (nx, ny) in choices:
                new_digits = digits + (digit,)
                new_bits = used_bits if digit is None else used_bits | (1 << digit[2])
                new_weight = weight + int(digit is not None)
                if not nx and not ny:
                    completed += 1
                    score = hybrid.model(new_digits)["m_plus_s_excluding_inversion"]
                    if best_score is None or score < best_score:
                        best_score, best = score, new_digits
                elif len(new_digits) < MAX_POSITIONS:
                    next_states.append((nx, ny, new_bits, new_digits, new_weight))
        if not next_states:
            break
        next_states.sort(key=rank)
        frontier = next_states[:width]
    fallback = hybrid.recode(*original, 63)
    fallback_score = hybrid.model(fallback)["m_plus_s_excluding_inversion"]
    if best_score is None or fallback_score < best_score:
        best, best_score = tuple(fallback), fallback_score
    assert hybrid.width4.expand(best) == original
    return list(best), {"expanded_states": expanded,
                        "distinct_transition_states": len(graph.nodes),
                        "completed_paths": completed, "beam_width": width,
                        "score": best_score, "width4_score": fallback_score}


def training(output, width):
    source = HERE / "hybrid-holdout-result.json"
    artifact = json.loads(source.read_text())
    assert artifact["verified"] and len(artifact["rows"]) == 64
    rows = []
    total = {"beam_score": 0, "width4_score": 0, "expanded_states": 0,
             "distinct_transition_states": 0, "completed_paths": 0}
    for row in artifact["rows"]:
        a, b = int(row["short_a_hex"], 16), int(row["short_b_hex"], 16)
        digits, info = search(a, b, width)
        assert hybrid.width4.expand(digits) == (a, b)
        assert info["width4_score"] == row["arms"]["width4"]["model"][
            "m_plus_s_excluding_inversion"]
        total["beam_score"] += info["score"]
        for key in ("width4_score", "expanded_states",
                    "distinct_transition_states", "completed_paths"):
            total[key] += info[key]
        rows.append({"index": row["index"], "short_a_hex": hex(a),
                     "short_b_hex": hex(b), "info": info,
                     "digit_length": len(digits),
                     "digit_weight": sum(d is not None for d in digits),
                     "used_seed_indices": hybrid.model(digits)["used_seed_indices"]})
    result = {
        "schema": 1, "kind": "retrospective-position-adaptive-training",
        "label": LABEL, "beam_width": width,
        "training_input_sha256": artifact["input_sha256"],
        "training_artifact_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "rows": rows, "totals": total,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cpu_speedup_claim": None, "academic_novelty_claim": None,
    }
    if output.exists():
        raise SystemExit("training result exists; refusing overwrite")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(rows), "totals": total,
                      "saving_per_scalar": (
                          total["width4_score"] - total["beam_score"]) / len(rows)},
                     sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--beam-width", type=int, default=BEAM_WIDTH)
    args = parser.parse_args()
    if args.beam_width < 1:
        parser.error("beam width must be positive")
    training(args.train, args.beam_width)


if __name__ == "__main__":
    main()
