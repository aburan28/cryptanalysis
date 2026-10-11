#!/usr/bin/env python3
"""Select four-corner scalar paths with an optional two-point terminal."""

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load("terminal_split_prior", ROOT / "prime-j0-budget-optimal-20261011/replay_holdout.py")
phase = load("terminal_split_terminal", ROOT / "prime-j0-carry-aware-v2-20261011/phase_cost.py")
screen = prior.dual.screen
dual = prior.dual
COVER = ROOT / "prime-j0-budget-optimal-20261011/cover-budget-optimal.bin"
TERMINAL = phase.TERMINAL
BOUND = 149
RADIX = 1024
ROWS = 12


def digest(raw):
    return sha256(raw).hexdigest()


def representatives(scalar):
    """Return the old nearest-norm choice first, then the other corners."""
    scalar %= screen.ORDER
    fw = scalar * screen.V[1] // screen.ORDER
    fv = -(scalar * screen.W[1]) // screen.ORDER
    corners = {
        (scalar - i * screen.W[0] - j * screen.V[0],
         -i * screen.W[1] - j * screen.V[1])
        for i in (fw, fw + 1) for j in (fv, fv + 1)
    }
    old = screen.representative(scalar)
    assert old in corners and len(corners) == 4
    return [old, *sorted(corners - {old})]


def recode_pair(pair, assignments, seeds, canonical, node_index):
    a, b = pair
    place = 1
    reconstructed = [0, 0]
    digits = []
    for _ in range(ROWS):
        node = canonical[(a % RADIX) * RADIX + b % RADIX]
        seed_id, exponent = assignments[node_index[node]]
        assert 0 <= exponent < 3
        mapped = dual.mapped(seeds[seed_id], exponent)
        matches = [(unit, digit) for unit, digit in enumerate(screen.units(mapped))
                   if digit[0] % RADIX == a % RADIX
                   and digit[1] % RADIX == b % RADIX]
        assert matches
        unit, digit = matches[0]
        assert screen.norm(digit) <= dual.NORM_LIMIT
        digits.append([digit[0], digit[1], seed_id, exponent, unit])
        reconstructed[0] += place * digit[0]
        reconstructed[1] += place * digit[1]
        a, b = (a - digit[0]) // RADIX, (b - digit[1]) // RADIX
        place *= RADIX
    reconstructed[0] += place * a
    reconstructed[1] += place * b
    assert tuple(reconstructed) == pair
    return {"representative": list(pair), "digits": digits, "terminal": [a, b]}


def terminal_splits(terminal):
    a, b = terminal
    if screen.norm((a, b)) < BOUND * BOUND:
        return [((a, b),)]
    if screen.norm((a, b)) >= (2 * BOUND) ** 2:
        return []
    choices = []
    for x in sorted({a // 2, (a + 1) // 2}):
        for y in sorted({b // 2, (b + 1) // 2}):
            first = (x, y)
            second = (a - x, b - y)
            split = (first, second)
            if first != (0, 0) and second != (0, 0) and all(
                screen.norm(point) < BOUND * BOUND for point in split
            ) and split not in choices:
                choices.append(split)
    return choices


def metrics(path, parts, terminal_raw):
    masks = [0, 0, 0]
    terms = 0
    for _, _, seed, exponent, unit in path["digits"]:
        if seed:
            masks[exponent] |= 1 << (unit // 2)
            terms += 1
    for a, b in parts:
        seed, exponent, unit = phase.terminal_code(terminal_raw, a, b)
        if seed:
            masks[exponent] |= 1 << (unit // 2)
            terms += 1
    occupied = sum(bool(mask) for mask in masks)
    rotations = sum(mask.bit_count() - 1 + int(not mask & 1)
                    for mask in masks if mask)
    mixed = terms - occupied
    merges = max(occupied - 1, 0)
    proxy = (11 * mixed + 14 * merges + 6 * bool(masks[1])
             + 10 * bool(masks[2]) + rotations)
    return {"point_proxy_units": proxy, "terms": terms,
            "mixed_additions": mixed, "bucket_merges": merges,
            "occupied_buckets": occupied, "tau1_active": int(bool(masks[1])),
            "tau2_active": int(bool(masks[2])),
            "grouped_rotations": rotations, "unit_masks": masks}


def rank(option, baseline_pair):
    pair = tuple(option["path"]["representative"])
    return (option["metrics"]["point_proxy_units"],
            len(option["terminal_parts"]), int(pair != baseline_pair),
            screen.norm(pair), pair, tuple(map(tuple, option["terminal_parts"])))


def one_scalar(scalar, assignments, seeds, canonical, node_index, terminal_raw):
    choices = representatives(scalar)
    options = []
    for pair in choices:
        path = recode_pair(pair, assignments, seeds, canonical, node_index)
        for parts in terminal_splits(path["terminal"]):
            options.append({"path": path, "terminal_parts": [list(p) for p in parts],
                            "metrics": metrics(path, parts, terminal_raw)})
    assert options and tuple(options[0]["path"]["representative"]) == choices[0]
    assert len(options[0]["terminal_parts"]) == 1
    selected = min(range(len(options)), key=lambda i: rank(options[i], choices[0]))
    return {"baseline_option": 0, "selected_option": selected,
            "recode_attempts": 4, "options": options}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=HERE / "holdout-inputs.json")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    input_raw = args.inputs.read_bytes()
    inputs = json.loads(input_raw)
    if "candidate_source_sha256" in inputs and "replay.py" in inputs["candidate_source_sha256"]:
        assert inputs["candidate_source_sha256"]["replay.py"] == digest(Path(__file__).read_bytes())
    cover_raw, assignments, seeds = prior.load_cover(COVER, 83_878, 7)
    terminal_raw = TERMINAL.read_bytes()
    if "cover_sha256" in inputs:
        assert digest(cover_raw) == inputs["cover_sha256"]
    if "terminal_sha256" in inputs:
        assert digest(terminal_raw) == inputs["terminal_sha256"]
    canonical, nodes, _, _ = dual.parent.full_classes()
    node_index = {node: index for index, node in enumerate(nodes)}
    scalars = inputs["scalars_hex"][:args.limit]
    totals = {"baseline": Counter(), "selected": Counter()}
    selected_split = changed = improved = 0
    lines = []
    for index, text in enumerate(scalars):
        record = one_scalar(int(text, 16), assignments, seeds, canonical,
                            node_index, terminal_raw)
        baseline = record["options"][0]
        selected = record["options"][record["selected_option"]]
        for name, option in (("baseline", baseline), ("selected", selected)):
            totals[name].update({key: value for key, value in option["metrics"].items()
                                 if key != "unit_masks"})
        selected_split += len(selected["terminal_parts"]) == 2
        changed += record["selected_option"] != 0
        improved += selected["metrics"]["point_proxy_units"] < baseline["metrics"]["point_proxy_units"]
        lines.append(json.dumps({"index": index, **record}, sort_keys=True, separators=(",", ":")))
    result = {"schema": 1, "status": "screened", "cases": len(lines),
              "recode_attempts": 4 * len(lines), "selected_split": selected_split,
              "selected_changed": changed, "point_proxy_improved": improved,
              "baseline": dict(sorted(totals["baseline"].items())),
              "selected": dict(sorted(totals["selected"].items())),
              "input_sha256": digest(input_raw), "cover_sha256": digest(cover_raw),
              "terminal_sha256": digest(terminal_raw),
              "source_sha256": digest(Path(__file__).read_bytes())}
    if not args.dry_run:
        output = HERE / "holdout-paths.jsonl"
        receipt = HERE / "holdout-screen.json"
        if output.exists() or receipt.exists():
            raise SystemExit("refusing to overwrite frozen result")
        raw = ("\n".join(lines) + "\n").encode()
        output.write_bytes(raw)
        result["certificate_sha256"] = digest(raw)
        receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("cases", "recode_attempts", "selected_split",
                       "selected_changed", "point_proxy_improved", "baseline",
                       "selected")}, sort_keys=True))


if __name__ == "__main__":
    main()
