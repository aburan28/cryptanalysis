#!/usr/bin/env python3
"""Independent operation and dependency screen for the gauge tree."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NATIVE = ROOT / "prime-j0-secp256k1-native"
INPUT = ROOT / "prime-j0-sector-digit-20261010/fresh-inputs.json"
SCREEN = NATIVE / "unit_orbit_windows_screen.py"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def serial_rotations(codes):
    powers = {code // 2 for code in codes}
    previous = None
    rotations = 0
    for power in (1, 2, 0):
        if power not in powers:
            continue
        rotations += int(previous is not None and previous != power)
        previous = power
    return rotations + int(previous is not None and previous != 0)


def tree(codes):
    # (product depth, gauge, affine). The Rust selector uses the same
    # lexicographic score and retains original node order on ties.
    nodes = [(0, code // 2, True) for code in codes]
    work = rotations = 0
    while len(nodes) > 1:
        candidates = []
        for i, a in enumerate(nodes):
            for j in range(i + 1, len(nodes)):
                b = nodes[j]
                products = 6 if a[2] and b[2] else 10 if a[2] or b[2] else 14
                for gauge in (a[1], b[1]):
                    ra, rb = int(a[1] != gauge), int(b[1] != gauge)
                    depth = max(a[0] + ra, b[0] + rb) + products
                    candidates.append((depth, products + ra + rb, gauge, i, j, ra + rb))
        depth, cost, gauge, i, j, turns = min(candidates)
        work += cost
        rotations += turns
        nodes = [node for k, node in enumerate(nodes) if k not in (i, j)]
        nodes.append((depth, gauge, False))
    depth, gauge, _ = nodes[0]
    work += int(gauge != 0)
    rotations += int(gauge != 0)
    return work, rotations, depth + int(gauge != 0)


def main():
    sys.path.insert(0, str(NATIVE.resolve()))
    spec = importlib.util.spec_from_file_location("gauge_tree_screen", SCREEN)
    screen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(screen)
    inputs = json.loads(INPUT.read_text())
    atlases = {width: screen.OrbitAtlas(width) for width in (9, 10)}
    totals = Counter()
    for scalar_hex in inputs["scalars_hex"]:
        scalar = int(scalar_hex, 16)
        representative = tuple(screen.hex_choices(scalar)[0][2:4])
        codes = [unit for _, unit, active in screen.recode(representative, atlases)
                 if active]
        work, rotations, depth = tree(codes)
        totals.update(cases=1, terms=len(codes), tree_field_products=work,
                      tree_rotations=rotations, product_depth=depth,
                      serial_field_products=10 * (len(codes) - 1) + serial_rotations(codes),
                      serial_rotations=serial_rotations(codes))
    assert totals["cases"] == 4096
    log = (HERE / "panel-test.txt").read_text()
    match = re.search(r"gauge_tree_cases=(\d+) rotations=(\d+) serial_rotations=(\d+) "
                      r"tree_field_products=(\d+) serial_field_products=(\d+) "
                      r"product_depth=(\d+)", log)
    assert match, "missing native panel counts"
    assert tuple(map(int, match.groups())) == tuple(totals[key] for key in (
        "cases", "tree_rotations", "serial_rotations", "tree_field_products",
        "serial_field_products", "product_depth"))
    result = {"schema": 1, "kind": "source-formula-product-and-depth-screen",
              "status": "independently_replayed", "totals": dict(sorted(totals.items())),
              "input_sha256": digest(INPUT), "screen_sha256": digest(SCREEN),
              "native_panel_log_sha256": digest(HERE / "panel-test.txt"),
              "source_sha256": digest(Path(__file__))}
    (HERE / "model.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["totals"], sort_keys=True))


if __name__ == "__main__":
    main()
