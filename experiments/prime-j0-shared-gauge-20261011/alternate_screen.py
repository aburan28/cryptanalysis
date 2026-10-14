#!/usr/bin/env python3
"""Census admissible tau images of the existing quotient seed set."""

from collections import Counter, defaultdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUOTIENT = ROOT / "prime-j0-orbit-quotient-20261011"
SPEC = importlib.util.spec_from_file_location("quotient_alternates", QUOTIENT / "verify_group.py")
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    full_path = QUOTIENT / "atlas-r1024-full-orbit-quotient.bin"
    atlas = q.QuotientFullAtlas(full_path)
    options = defaultdict(list)
    image_count = 0
    for seed_id in range(atlas.count):
        seed = atlas.seed(seed_id)
        for exponent in range(3):
            digit = q.parent.tau_power(seed, exponent)
            if q.parent.screen.norm(digit) > 1024 * 1024:
                break
            canonical = min(q.residue(image) for image in q.unit_images(digit))
            options[canonical].append((seed_id, exponent))
            image_count += 1
    assigned_exponents = Counter()
    choices = Counter()
    lower_exponent = Counter()
    extra_by_assigned = Counter()
    for canonical, alternatives in options.items():
        a, b = divmod(canonical, 1024)
        _, assigned_seed, assigned_exponent, _ = atlas.decode(a, b)
        assert (assigned_seed, assigned_exponent) in alternatives
        assigned_exponents[assigned_exponent] += 1
        choices[len(alternatives)] += 1
        minimum = min(exponent for _, exponent in alternatives)
        if minimum < assigned_exponent:
            lower_exponent[(assigned_exponent, minimum)] += 1
        extra_by_assigned[assigned_exponent] += len(alternatives) - 1
    assert len(options) == 174_764
    receipt = {"schema": 1, "status": "screened",
               "timing_class": "construction_only",
               "source_sha256": digest(Path(__file__)),
               "atlas_sha256": digest(full_path),
               "seeds": atlas.count,
               "admissible_seed_images": image_count,
               "classes": len(options),
               "choice_multiplicity": dict(choices),
               "assigned_exponents": dict(assigned_exponents),
               "extra_choices_by_assigned_exponent": dict(extra_by_assigned),
               "lower_exponent_alternatives": {
                   f"{old}_to_{new}": count
                   for (old, new), count in lower_exponent.items()}}
    (HERE / "alternate-screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
