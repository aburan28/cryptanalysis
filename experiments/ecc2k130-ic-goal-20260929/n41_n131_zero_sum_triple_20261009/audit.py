#!/usr/bin/env python3
"""Independent Sage replay of zero-sum triple geometry and native rows."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))


def spectrum(values):
    # Recursive halves rather than the producer's in-place butterfly.
    if len(values) == 1:
        return values
    even = spectrum(values[::2])
    odd = spectrum(values[1::2])
    return [a + b for a, b in zip(even, odd)] + \
           [a - b for a, b in zip(even, odd)]


def parse_input(path):
    lines = Path(path).read_text().splitlines()
    head = list(map(int, lines[0].split()))
    position = 1
    blocks = []
    for expected_rotation in (0, 10, 20, 30):
        rotation, count = map(int, lines[position].split())
        assert rotation == expected_rotation and count == 126
        position += 1
        rows = [tuple(map(int, lines[position + i].split()))
                for i in range(count)]
        position += count
        blocks.append(rows)
    assert position == len(lines)
    return head, blocks


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    geometry = json.loads((HERE / "geometry_result.json").read_text())
    assert protocol["status"] == "FROZEN" and geometry["status"] == "EXACT_GEOMETRY"
    paths = {"prepare": HERE / "prepare.py", "join_source": HERE / "join.cpp",
             "join_binary": HERE / "join", "runner": HERE / "run.py",
             "audit": HERE / "audit.py",
             "runtime": HERE / "sage_runtime_info.json",
             "screen": GOAL / "n131_w18_four_pairs/screen.json",
             "geometry": HERE / "geometry_result.json",
             "n131_valid_bits": HERE / "n131_valid_mask_bits.bin",
             "input_control": HERE / "input_control.txt",
             "input_public": HERE / "input_public.txt",
             "control_witness": HERE / "control_witness.json",
             "helper": GOAL / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp"}
    assert all(sha(path) == protocol["sha256"][name]
               for name, path in paths.items())
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    field_poly = PolynomialRing(GF(2), "T")
    T = field_poly.gen()
    field = GF(2**41, name="T", modulus=T**41 + T**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(field_poly([(int(value) >> i) & 1 for i in range(41)]))

    def point(coords):
        return curve(decode(coords[0]), decode(coords[1]))

    def frob(value, rotation):
        for _ in range(rotation):
            value = curve(value[0]**2, value[1]**2)
        return value

    def half_trace(value):
        result = field.zero()
        for _ in range(21):
            result += value
            value = value**4
        return result

    source = {}
    valid = set()
    for mask in range(1, 128):
        w = sum((field(T**(i + 1)) for i in range(7) if mask >> i & 1),
                field.zero())
        h = half_trace(w)
        rational = (1 / w).trace() == 0
        roots = curve.lift_x(1 + 1 / h, all=True) if h not in (0, 1) else []
        assert rational == (len(roots) == 2)
        if rational:
            valid.add(mask)
            source[mask] = [(4 * root, root) for root in roots]
    assert len(valid) == geometry["n41"]["valid_masks"] == 63
    shapes = {tuple(sorted((a, b, a ^ b))) for a in valid for b in valid
              if a < b and a ^ b in valid}
    assert len(shapes) == geometry["n41"]["unordered_zero_sum_triples"] == 317
    valid_bits = (HERE / "n131_valid_mask_bits.bin").read_bytes()
    assert len(valid_bits) == (1 << 18) // 8
    bits = [(valid_bits[i >> 3] >> (i & 7)) & 1 for i in range(1 << 18)]
    assert bits[0] == 0 and sum(bits) == geometry["n131"]["valid_masks"] == 131307
    walsh = spectrum(bits)
    ordered = sum(value**3 for value in walsh) // (1 << 18)
    assert ordered % 6 == 0
    assert ordered // 6 == geometry["n131"]["unordered_zero_sum_triples"]
    assert max(abs(value) for value in walsh[1:]) == \
        geometry["n131"]["walsh_nontrivial_abs_max"]
    field131 = GF(2**131, name="T", modulus=T**131 + T**13 + T**2 + T + 1)
    basis131 = [field131(T**i) for i in range(1, 19)]
    checked = 0
    for mask in list(range(1, 129)) + [1 + (i * 7919) % ((1 << 18) - 1)
                                      for i in range(128)]:
        w = sum((basis131[i] for i in range(18) if mask >> i & 1),
                field131.zero())
        assert ((1 / w).trace() == 0) == bool(bits[mask])
        checked += 1

    base_ring = PolynomialRing(GF(2), names=("s", "p", "z"))
    s, p, z = base_ring.gens()
    aux_ring = PolynomialRing(base_ring, "X")
    X = aux_ring.gen()
    q = p*p + p*(s + 1)
    h = (q + 1)*X*X + q*X + s*s
    r = (s*s + s)*(z*z + z)
    k = (r + 1)*X*X + r*X + (s + z)**2
    quartic = base_ring(h.resultant(k))
    assert len(quartic.dict()) == geometry["quartic"]["term_count"] == 21
    assert [list(exponents) for exponents in sorted(quartic.dict())] == \
        geometry["quartic"]["terms"]
    assert quartic.coefficient({z: 3}) == p*s*(s + 1)*(s + p + 1)

    control_witness = json.loads((HERE / "control_witness.json").read_text())
    assert len(set(control_witness["columns"])) == 12
    assert sum((point(coords) for coords in control_witness["subgroup_points"]),
               curve(0)) == point(control_witness["target"])
    row_statuses = {}
    for mode in ("control", "public"):
        head, blocks = parse_input(HERE / f"input_{mode}.txt")
        assert head[2:] == [549756390943, 4]
        target = point(head[:2])
        assert 549756390943 * target == curve(0)
        assert len({tuple(row[:2]) for row in blocks[0]}) == 126
        for block, rows in enumerate(blocks):
            assert len(rows) == 126
            for mask, sign, column, x, y in rows:
                assert mask in valid and sign in (0, 1)
                assert point((x, y)) == frob(source[mask][sign][0], 10 * block)
        result = json.loads((HERE / mode / "result.json").read_text())
        terminal = json.loads((HERE / mode / "terminal.json").read_text())
        assert result["status"] == terminal["status"]
        assert terminal["result_sha256"] == sha(HERE / mode / "result.json")
        assert terminal["protocol_sha256"] == sha(HERE / "protocol.json")
        assert terminal["stdout_sha256"] == sha(HERE / mode / "stdout.txt")
        assert terminal["stderr_sha256"] == sha(HERE / mode / "stderr.txt")
        assert result["target"] == head[:2]
        assert result["setup_ns"] == (result["triple_build_ns"] +
                result["left_build_ns"] + result["left_sort_ns"])
        assert result["online_ns"] == result["query_ns"] + result["online_overhead_ns"]
        assert result["setup_ns"] < 300 * 10**9
        assert result["online_ns"] < 120 * 10**9
        assert result["peak_rss_bytes"] < 4 * 1024**3
        if result["status"] == "VERIFIED_RAW_ROW":
            row = result["row"]
            assert len(row) == 12 and len({leaf["column"] for leaf in row}) == 12
            group_points = []
            for block in range(4):
                leaves = row[3*block:3*block+3]
                masks = [leaf["mask"] for leaf in leaves]
                assert masks[0] ^ masks[1] ^ masks[2] == 0
                raw = []
                u = []
                for leaf in leaves:
                    source_point, source_raw = source[leaf["mask"]][leaf["sign"]]
                    subgroup = frob(source_point, 10 * block)
                    assert point(leaf["point"]) == subgroup
                    assert leaf["rotation"] == 10 * block
                    assert tuple(leaf["point"]) in \
                        [(r[3], r[4]) for r in blocks[block]
                         if r[:3] == (leaf["mask"], leaf["sign"], leaf["column"])]
                    group_points.append(subgroup)
                    raw.append(frob(source_raw, 10 * block))
                    w = sum((field(T**(i + 1)) for i in range(7)
                             if leaf["mask"] >> i & 1), field.zero())
                    u.append(half_trace(w)**(2**(10*block)))
                assert u[0] + u[1] + u[2] == 0
                raw_sum = sum(raw, curve(0))
                if raw_sum != curve(0) and raw_sum[0] != 1:
                    output = 1 / (raw_sum[0] + 1)
                    assert quartic(u[0]+u[1], u[0]*u[1], output) == 0
                    assert u[0]*u[1]*(u[0]+u[1])*(u[0]+u[1]+1)*\
                        (u[0]+u[1]+u[0]*u[1]+1) != 0
            assert sum(group_points, curve(0)) == target
            assert all(549756390943 * member == curve(0) for member in group_points)
        else:
            assert result["row"] is None
            assert result["status"] in ("SETUP_CAP", "ONLINE_CAP", "EXHAUSTED_NO_ROW")
        row_statuses[mode] = result["status"]
    assert row_statuses["control"] == "VERIFIED_RAW_ROW"
    receipt = {"status": "PASS_INDEPENDENT_SAGE_AUDIT",
               "n41_triple_shapes": len(shapes),
               "n131_triple_shapes": ordered // 6,
               "n131_field_mask_checks": checked,
               "row_statuses": row_statuses,
               "protocol_sha256": sha(HERE / "protocol.json")}
    (HERE / "audit.json").write_text(json.dumps(receipt, indent=2,
                                               sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
