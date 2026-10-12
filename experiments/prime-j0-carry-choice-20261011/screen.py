#!/usr/bin/env python3
"""Oracle screen for carry-aware choices from already stored seed points."""

from collections import Counter, defaultdict
from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ADIC = ROOT / "prime-j0-adic-orbit-20261011"
SPEC = importlib.util.spec_from_file_location("adic_carry_control", ADIC / "verify_group.py")
adic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adic)
RADIX = 1024
FIRST_BRANCH_WINDOW = 6


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def unit_inverse_compose(canonical_unit, transform):
    return 2 * ((canonical_unit // 2 - transform // 2) % 3) \
        + ((canonical_unit & 1) ^ (transform & 1))


class AlternateAtlas:
    def __init__(self, path):
        self.base = adic.AdicFullAtlas(path)
        self.digest = digest(path)
        self.alternates = defaultdict(list)
        self.seed_images = 0
        for seed_id in range(self.base.count):
            seed = self.base.seed(seed_id)
            for exponent in range(3):
                digit = adic.q.parent.tau_power(seed, exponent)
                if adic.q.parent.screen.norm(digit) > RADIX * RADIX:
                    break
                if seed_id == 0 and exponent:
                    continue
                residue = digit[0] % RADIX, digit[1] % RADIX
                class_index, unit = adic.index.canonicalize(*residue)
                self.alternates[class_index].append((seed_id, exponent, unit))
                self.seed_images += 1
        assert len(self.alternates) == 174_764
        assert all(len(codes) <= 2 for codes in self.alternates.values())

    def options(self, ra, rb):
        baseline = self.base.decode(ra, rb)
        class_index, transform = adic.index.canonicalize(ra, rb)
        output = [baseline]
        for seed_id, exponent, canonical_unit in self.alternates[class_index]:
            unit = unit_inverse_compose(canonical_unit, transform)
            digit = adic.q.parent.reference.coord_unit(
                adic.q.parent.tau_power(self.base.seed(seed_id), exponent), unit)
            assert (digit[0] % RADIX, digit[1] % RADIX) == (ra, rb)
            candidate = (digit, seed_id, exponent, unit)
            if candidate not in output:
                output.append(candidate)
        assert len(output) <= 2
        return output


def group_cost(choices):
    terms = [choice for choice in choices if choice[0] != 0]
    powers = [set(), set(), set()]
    for _, exponent, unit in terms:
        powers[exponent].add(unit // 2)
    gauge = sum(len(bucket) - 1 + (0 not in bucket)
                for bucket in powers if bucket)
    outer_tau = int(bool(powers[1] or powers[2])) + int(bool(powers[2]))
    return max(0, len(terms) - 1), outer_tau, gauge


def baseline_path(representative, full, terminal):
    a, b = representative
    choices = []
    for _ in range(12):
        digit, seed, exponent, unit = full.decode(a, b)
        choices.append((seed, exponent, unit))
        a, b = (a - digit[0]) >> 10, (b - digit[1]) >> 10
    digit, seed, exponent, unit = terminal.decode(a, b)
    assert digit == (a, b)
    choices.append((seed, exponent, unit))
    return choices


def screen_case(representative, atlas, terminal):
    a, b = representative
    prefix = []
    for _ in range(FIRST_BRANCH_WINDOW):
        digit, seed, exponent, unit = atlas.base.decode(a, b)
        prefix.append((seed, exponent, unit))
        a, b = (a - digit[0]) >> 10, (b - digit[1]) >> 10
    states = [(a, b, tuple(prefix), 0)]
    explored = 0
    for _ in range(FIRST_BRANCH_WINDOW, 12):
        next_states = []
        for a, b, choices, changes in states:
            options = atlas.options(a % RADIX, b % RADIX)
            for position, (digit, seed, exponent, unit) in enumerate(options):
                assert (a - digit[0]) % RADIX == (b - digit[1]) % RADIX == 0
                next_states.append(((a - digit[0]) >> 10,
                                    (b - digit[1]) >> 10,
                                    choices + ((seed, exponent, unit),),
                                    changes + (position != 0)))
                explored += 1
        states = next_states
    valid = 0
    invalid_terminal = 0
    best = None
    best_changes = None
    for a, b, choices, changes in states:
        if adic.q.parent.screen.norm((a, b)) >= 149 * 149:
            invalid_terminal += 1
            continue
        try:
            digit, seed, exponent, unit = terminal.decode(a, b)
        except AssertionError:
            invalid_terminal += 1
            continue
        assert digit == (a, b)
        valid += 1
        candidate = group_cost(choices + ((seed, exponent, unit),))
        order = (*candidate, changes)
        if best is None or order < (*best, best_changes):
            best, best_changes = candidate, changes
    assert valid >= 1
    baseline = group_cost(baseline_path(representative, atlas.base, terminal))
    assert (*best, best_changes) <= (*baseline, 0)
    return baseline, best, best_changes, explored, valid, invalid_terminal


def main():
    global FIRST_BRANCH_WINDOW
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-window", type=int, default=6)
    args = parser.parse_args()
    assert 0 <= args.first_window <= 12
    FIRST_BRANCH_WINDOW = args.first_window
    panel_path = ADIC / "fresh-inputs.json"
    panel = json.loads(panel_path.read_bytes())
    scalars = [int(value, 16) for value in panel["scalars_hex"]]
    assert len(scalars) == 4096
    atlas_path = ADIC / "atlas-r1024-full-adic-orbit.bin"
    terminal_path = ADIC / "atlas-r1024-terminal-adic-orbit.bin"
    atlas = AlternateAtlas(atlas_path)
    terminal = adic.q.parent.TerminalAtlas(terminal_path)
    counts = Counter()
    savings = Counter()
    examples = []
    for case, scalar in enumerate(scalars):
        representative = adic.q.parent.screen.representative(
            scalar % adic.q.parent.screen.ORDER)
        baseline, best, changes, explored, valid, invalid = screen_case(
            representative, atlas, terminal)
        counts["baseline_mixed_additions"] += baseline[0]
        counts["oracle_mixed_additions"] += best[0]
        counts["baseline_outer_tau"] += baseline[1]
        counts["oracle_outer_tau"] += best[1]
        counts["baseline_gauge_rotations"] += baseline[2]
        counts["oracle_gauge_rotations"] += best[2]
        counts["explored_partial_states"] += explored
        counts["valid_full_paths"] += valid
        counts["invalid_terminal_paths"] += invalid
        counts["cases_with_multiple_valid_paths"] += valid > 1
        counts["cases_changed"] += changes > 0
        savings[baseline[0] - best[0]] += 1
        if baseline[0] > best[0] and len(examples) < 16:
            examples.append({"case_index": case, "mixed_additions_saved":
                             baseline[0] - best[0], "choice_changes": changes})
    group = json.loads((ADIC / "group-check.json").read_bytes())["results"]["adic"]
    assert counts["baseline_mixed_additions"] == group["mixed_additions"]
    assert counts["baseline_outer_tau"] == group["outer_tau_images"]
    assert counts["baseline_gauge_rotations"] == group["gauge_rotations"]
    multiplicity = Counter(map(len, atlas.alternates.values()))
    receipt = {"schema": 1, "status": "screened",
               "timing_class": "oracle_operation_count_only",
               "source_sha256": digest(Path(__file__)),
               "panel_sha256": digest(panel_path),
               "atlas_sha256": atlas.digest,
               "terminal_sha256": digest(terminal_path),
               "first_branch_window": FIRST_BRANCH_WINDOW,
               "seed_images": atlas.seed_images,
               "class_choice_multiplicity": dict(multiplicity),
               "extra_codes": sum(max(0, size - 1) * count
                                  for size, count in multiplicity.items()),
               "counts": dict(counts),
               "addition_saving_histogram": dict(savings),
               "examples": examples}
    (HERE / f"screen-w{FIRST_BRANCH_WINDOW}.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
