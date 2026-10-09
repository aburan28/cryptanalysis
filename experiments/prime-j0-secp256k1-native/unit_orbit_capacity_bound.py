#!/usr/bin/env python3
"""Exact counting bound for fixed-slot six-unit fixed-base point tables."""

import json
from pathlib import Path


ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
POINT_BYTES = 72
CAP_BYTES = 90 * (1 << 20)
UNITS = 6
WIDTHS14 = (10, 10, 10) + (9,) * 11


def max_outputs(point_slots, positions):
    """Maximum selection count with balanced, independently charged tables."""
    small, extra = divmod(point_slots, positions)
    return ((1 + UNITS * small) ** (positions - extra)
            * (1 + UNITS * (small + 1)) ** extra)


def first_sufficient_slots(positions):
    lower = 0
    upper = 1
    while max_outputs(upper, positions) < ORDER:
        upper *= 2
    while lower < upper:
        middle = (lower + upper) // 2
        if max_outputs(middle, positions) >= ORDER:
            upper = middle
        else:
            lower = middle + 1
    return lower


def main():
    slots_under_cap = CAP_BYTES // POINT_BYTES
    threshold13 = first_sufficient_slots(13)
    orbit_slots14 = sum(((1 << (2 * width)) + 8) // 6 for width in WIDTHS14)
    assert sum(WIDTHS14) == 129
    assert max_outputs(slots_under_cap, 13) < ORDER
    assert max_outputs(slots_under_cap, 14) >= ORDER
    assert max_outputs(threshold13 - 1, 13) < ORDER <= max_outputs(threshold13, 13)
    assert orbit_slots14 == 1_004_904
    assert orbit_slots14 * POINT_BYTES < CAP_BYTES
    result = {
        "schema": 1,
        "curve": "secp256k1",
        "group_order_hex": f"{ORDER:064x}",
        "point_bytes": POINT_BYTES,
        "cap_bytes": CAP_BYTES,
        "point_slots_under_cap": slots_under_cap,
        "unit_images_per_stored_point": UNITS,
        "implicit_identity_per_position": True,
        "thirteen_slot_max_outputs_decimal": str(max_outputs(slots_under_cap, 13)),
        "thirteen_slot_covers_group": False,
        "fourteen_slot_counting_bound_covers_group": True,
        "minimum_slots_for_thirteen_positions": threshold13,
        "minimum_point_bytes_for_thirteen_positions": threshold13 * POINT_BYTES,
        "u14_windows": list(WIDTHS14),
        "u14_stored_point_slots": orbit_slots14,
        "u14_stored_point_bytes": orbit_slots14 * POINT_BYTES,
        "scope": "one lookup from each of a fixed set of independent, separately charged positional tables; at most six unit images of a point plus an implicit identity",
    }
    output = Path(__file__).with_name("unit-orbit-capacity-bound.json")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"thirteen_slot_covers_group": False,
                      "minimum_slots_for_thirteen_positions": threshold13,
                      "u14_stored_point_slots": orbit_slots14}, sort_keys=True))


if __name__ == "__main__":
    main()
