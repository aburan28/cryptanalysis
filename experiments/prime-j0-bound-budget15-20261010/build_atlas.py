#!/usr/bin/env python3
"""Build the full width-nine tau atlas and prove the fifteen-window bound."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
source = HERE.parent / "prime-j0-tau-power16-20261010" / "screen.py"
spec = importlib.util.spec_from_file_location("tau_power16_screen", source)
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)
screen.HERE = HERE
screen.LIMITS = {9: 512}

widths = (8,) * 6 + (9,) * 9
bounds = (256,) * 6 + (512,) * 8 + (363,)
product = 1
digit_sum = 0
for width, bound in zip(widths, bounds):
    digit_sum += bound * product
    product <<= width
margin = 3 * (product - digit_sum) ** 2 - screen.ORDER
assert product == 1 << 129
assert product > digit_sum and margin > 0

_, _, atlas = screen.build_atlas(9)
assert atlas["seed_count"] == 21_847
assert atlas["atlas_bytes"] == 1_135_972
assert atlas["eligible_classes"] == atlas["unit_classes"] == 43_692
receipt = {
    "atlas": atlas,
    "atlas_generator_sha256": sha256(source.read_bytes()).hexdigest(),
    "widths": list(widths),
    "digit_length_bounds": list(bounds),
    "radix_product": str(product),
    "weighted_digit_bound": str(digit_sum),
    "termination_margin": str(margin),
    "table_seeds": 6 * 5_463 + 8 * atlas["seed_count"] + 25_869,
}
(HERE / "atlas-receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n"
)
print(json.dumps(receipt, sort_keys=True))
