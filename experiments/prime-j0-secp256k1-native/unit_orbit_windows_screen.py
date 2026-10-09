#!/usr/bin/env python3
"""Exact unit-orbit radix table and frozen point-operation screen."""

import argparse
from array import array
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess

from check_eisenstein_scalar_fixed import scalar_text
from graph_aware_cover_screen import representatives
from hex9_cover_screen import hex_choices
from screen_coset_representatives import LAMBDA_TAU, N
from tau6_comb13_sparse_screen import SPARSE_TOP_ORBITS
from width6_tau_screen import build_width_six_table


HERE = Path(__file__).resolve().parent
WIDTHS = (10,) * 3 + (9,) * 11
SEEDS = {"design": 20261009511, "holdout": 20261009512}
COUNTS = {"design": 2048, "holdout": 4096}
SLOT_BYTES = 72
MAP_WORD_BYTES = 4
LIMIT_BYTES = 90 * (1 << 20)
UNSET = (1 << 32) - 1
BASELINE_SHA256 = "fbd46d82b7b7867b4bf71dedc46b8ef8a43dd552a94b3779158b347ee1e40b80"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def omega(pair):
    a, b = pair
    return a + 3 * b, -a - 2 * b


def unit_images(pair):
    result = []
    value = pair
    for _ in range(3):
        result.extend((value, (-value[0], -value[1])))
        value = omega(value)
    assert value == pair
    assert all(norm(image) == norm(pair) for image in result)
    return result


def nearest_digit(residue, base):
    # (u,v)=(a+b,-b) gives the equilateral norm u^2-u*v+v^2.
    a, b = residue
    u, v = a + b, -b
    floor_u, floor_v = u // base, v // base
    options = []
    for m in (floor_u, floor_u + 1):
        for n in (floor_v, floor_v + 1):
            x, y = u - m * base, v - n * base
            digit = (x + y, -y)
            options.append((norm(digit), digit))
    best_norm, digit = min(options)
    assert best_norm * 3 <= base * base
    assert digit[0] % base == a and digit[1] % base == b
    return digit


class OrbitAtlas:
    def __init__(self, width):
        self.width = width
        self.base = 1 << width
        base = self.base
        self.codes = array("I", [UNSET]) * (base * base)
        self.digits = []
        for index in range(base * base):
            if self.codes[index] != UNSET:
                continue
            residue = divmod(index, base)
            orbit = [(a % base, b % base) for a, b in unit_images(residue)]
            assert residue == min(orbit)
            orbit_id = len(self.digits)
            self.digits.append(nearest_digit(residue, base))
            for unit_code, (a, b) in enumerate(orbit):
                slot = a * base + b
                if self.codes[slot] == UNSET:
                    self.codes[slot] = (orbit_id << 3) | unit_code
        expected = (base * base + 8) // 6
        assert len(self.digits) == expected
        assert all(code != UNSET for code in self.codes)
        assert self.digits[0] == (0, 0)

    def digit(self, pair):
        base = self.base
        a, b = pair
        residue = (a % base, b % base)
        code = self.codes[residue[0] * base + residue[1]]
        orbit_id, unit_code = code >> 3, code & 7
        assert unit_code < 6
        digit = unit_images(self.digits[orbit_id])[unit_code]
        assert digit[0] % base == residue[0] and digit[1] % base == residue[1]
        return digit, orbit_id, unit_code

    def receipt(self):
        digest = hashlib.sha256()
        for digit in self.digits:
            digest.update(struct.pack("<hh", *digit))
        return {"width": self.width, "base": self.base,
                "orbits": len(self.digits), "canonical_digits_sha256": digest.hexdigest(),
                "residue_map_sha256": hashlib.sha256(self.codes.tobytes()).hexdigest()}


def recode(pair, atlases):
    start = pair
    reconstructed = (0, 0)
    factor = 1
    windows = []
    for width in WIDTHS:
        atlas = atlases[width]
        digit, orbit_id, unit_code = atlas.digit(pair)
        reconstructed = (reconstructed[0] + factor * digit[0],
                         reconstructed[1] + factor * digit[1])
        pair = ((pair[0] - digit[0]) // atlas.base,
                (pair[1] - digit[1]) // atlas.base)
        windows.append((orbit_id, unit_code, digit != (0, 0)))
        factor *= atlas.base
    assert factor == 1 << 129
    assert pair == (0, 0), (start, pair)
    assert reconstructed == start
    return windows


def baseline_check(binary, scalars, expected):
    process = subprocess.run(
        [str(binary), "--scalar-w6-comb13-hex9-graphaware33-fixed"],
        input="".join(scalar_text(scalar) + "\n" for scalar in scalars),
        capture_output=True, text=True, check=True, timeout=900)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(expected)
    for index, (row, (selected, valid)) in enumerate(zip(rows, expected)):
        work = row["recoding_work"]
        assert list(map(int, row["representative"])) == selected["representative"], index
        assert row["tau_steps"] == selected["tau_steps"], index
        assert row["nonzero_digits"] == selected["mixed_additions"] - selected["fusions"], index
        assert work["top_repaired"] == selected["top_repaired"], index
        assert work["pair_fusions"] == selected["fusions"], index
        assert work["coset_rank"] == selected["rank"], index
        assert work["valid_representatives"] == valid, index
        assert work["attempted_representatives"] == 9, index
        assert selected["matched_proxy"] == 5 * row["tau_steps"] + 11 * row["nonzero_digits"], index


def screen(panel, binary, output):
    assert sha(binary) == BASELINE_SHA256
    if output.exists():
        raise SystemExit("output exists")
    if panel == "holdout":
        design = json.loads((HERE / "unit-orbit-windows-design.json").read_text())
        assert design["panel"] == "design" and design["status"] == "design_complete"
        assert design["protocol_sha256"] == sha(HERE / "UNIT_ORBIT_WINDOWS_PROTOCOL.md")
        assert design["screen_sha256"] == sha(Path(__file__))
    atlases = {width: OrbitAtlas(width) for width in set(WIDTHS)}
    points = sum(len(atlases[width].digits) for width in WIDTHS)
    table_bytes = points * SLOT_BYTES
    map_bytes = sum(len(atlas.codes) * MAP_WORD_BYTES for atlas in atlases.values())
    retained_bytes = table_bytes + map_bytes
    assert points == 1004904 and table_bytes == 72353088
    assert map_bytes == 5242880 and retained_bytes == 77595968
    assert retained_bytes < LIMIT_BYTES
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    selected_orbits = set(SPARSE_TOP_ORBITS)
    rng = random.Random(SEEDS[panel])
    scalars = [rng.randrange(N) for _ in range(COUNTS[panel])]
    input_hash = hashlib.sha256(b"".join(x.to_bytes(32, "big") for x in scalars)).hexdigest()
    totals = Counter()
    deltas = Counter()
    rows = []
    native_expected = []
    for index, scalar in enumerate(scalars):
        representative = hex_choices(scalar)[0][2:4]
        assert norm(representative) * 3 <= N
        assert (representative[0] + representative[1] * LAMBDA_TAU - scalar) % N == 0
        windows = recode(representative, atlases)
        nonidentity = sum(active for _, _, active in windows)
        candidate_proxy = 11 * max(nonidentity - 1, 0)
        _, parent, valid = representatives(scalar, table, selected_orbits)
        reference_proxy = parent["matched_proxy"]
        delta = reference_proxy - candidate_proxy
        totals.update(cases=1, reference_proxy=reference_proxy,
                      candidate_proxy=candidate_proxy,
                      candidate_nonidentity_windows=nonidentity,
                      reference_tau_steps=parent["tau_steps"],
                      reference_mixed_additions=parent["mixed_additions"] - parent["fusions"],
                      wins=int(delta > 0), regressions=int(delta < 0), ties=int(delta == 0))
        deltas[delta] += 1
        rows.append({"index": index, "scalar_sha256": hashlib.sha256(
            scalar.to_bytes(32, "big")).hexdigest(),
            "representative": [str(x) for x in representative],
            "reference_proxy": reference_proxy, "candidate_proxy": candidate_proxy,
            "nonidentity_windows": nonidentity,
            "orbit_units": [[orbit, unit] for orbit, unit, _ in windows]})
        if index < 128:
            native_expected.append((parent, valid))
    baseline_check(binary, scalars[:128], native_expected)
    gain = totals["reference_proxy"] - totals["candidate_proxy"]
    passed = gain * 5 >= totals["reference_proxy"]
    result = {"schema": 1, "panel": panel,
              "status": "design_complete" if panel == "design" else
                        ("screen_passed" if passed else "screen_stopped"),
              "seed": SEEDS[panel], "count": COUNTS[panel],
              "scalar_input_sha256": input_hash,
              "protocol_sha256": sha(HERE / "UNIT_ORBIT_WINDOWS_PROTOCOL.md"),
              "screen_sha256": sha(Path(__file__)),
              "baseline_binary_sha256": sha(binary),
              "widths": WIDTHS, "atlases": [atlases[w].receipt() for w in sorted(atlases)],
              "table_points_including_identity": points,
              "table_bytes_at_72_per_point": table_bytes,
              "residue_map_bytes_at_4_per_entry": map_bytes,
              "retained_bytes_at_declared_layout": retained_bytes,
              "gain_percent": 100 * gain / totals["reference_proxy"],
              "native_baseline_checks": 128,
              "exact_integer_reconstructions": COUNTS[panel],
              "totals": dict(totals),
              "delta_counts": dict(sorted(deltas.items())), "rows": rows}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"panel": panel, "status": result["status"],
                      "gain_percent": result["gain_percent"],
                      "table_bytes": table_bytes, "map_bytes": map_bytes,
                      "totals": dict(totals), "receipt_sha256": sha(output)}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", choices=SEEDS, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    screen(args.panel, args.binary.resolve(strict=True), args.output)


if __name__ == "__main__":
    main()
