#!/usr/bin/env sage -python
"""Independent installed-Sage audit of seven diagonal blocks and control."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SCREEN = HERE.parent / "n131_w18_four_pairs/screen.json"
R = 549756390943


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    output = HERE / "sage_preflight_audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol.json").read_text())
    planted = json.loads((HERE / "planted.json").read_text())
    receipt = json.loads((HERE / "preflight/receipt.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    screen = json.loads(SCREEN.read_text())["n41"]
    if (runtime["status"] != "verified" or
            receipt["status"] != "PASS_FULL_FORMULA_AND_GROUP_CONTROL" or
            receipt["protocol_sha256"] != sha(HERE / "protocol.json") or
            receipt["planted_sha256"] != sha(HERE / "planted.json") or
            receipt["formula"]["sha256"] != sha(HERE / "preflight/system.xcnf") or
            protocol["source_sha256"]["screen"] != sha(SCREEN) or
            protocol["curve_id"] != screen["curve_id"] or
            protocol["target_count"] != 1 or
            protocol["same_sign_only"] is not True):
        raise ValueError("frozen Sage control input changed")

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)

    def decode(value):
        return field(ring([(int(value) >> bit) & 1 for bit in range(41)]))

    def encode(value):
        return sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))

    def point(values):
        return curve(decode(values[0]), decode(values[1]))

    def key(p):
        if p == zero:
            raise ValueError("identity point in base or control")
        return (encode(p[0]), encode(p[1]))

    def frob(p, count):
        for _ in range(count):
            p = curve(p[0]**2, p[1]**2)
        return p

    def phi(p):
        if p == zero or p[0] == 1:
            raise ValueError("undefined transformed coordinate")
        return 1 / (p[0] + 1)

    source = {}
    columns = {}
    for x, y, column, mask, branch, sign in screen["point_rows_by_unique_rotation"]["0"]:
        if branch != 0 or sign not in (0, 1):
            raise ValueError("unexpected projected source branch")
        p = point((x, y))
        if p == zero or R * p != zero:
            raise ValueError("source point outside prime subgroup")
        source[(mask, sign)] = p
        if mask in columns and columns[mask] != column:
            raise ValueError("inconsistent folded column")
        columns[mask] = column
    if len(source) != 64 or len(columns) != 32 or len(set(columns.values())) != 26:
        raise ValueError("source mask geometry changed")

    base_points = set()
    for rotation in protocol["rotations"]:
        for source_point in source.values():
            p = frob(source_point, rotation)
            fp = frob(p, 1)
            base_points.add(key(p))
            base_points.add(key(fp))
    if (len(base_points) != protocol["actual_factor_base_points_B"] or
            protocol["effective_folded_columns_K"] != 26):
        raise ValueError("actual base size or folded columns changed")

    basis_w = [decode(value) for value in screen["window_basis_w"][0]]
    diagonal = []
    for i, (mask, sign, leaves, saved_sum) in enumerate(zip(
            planted["masks"], planted["signs"], planted["raw_leaves"],
            planted["diagonal_points"])):
        p, fp = (point(row) for row in leaves)
        if fp != frob(p, 1):
            raise ValueError("raw Frobenius pair changed")
        if 4 * p != frob(source[(mask, sign)], protocol["rotations"][i]):
            raise ValueError("raw source lift changed")
        if 4 * p == zero or R * (4 * p) != zero:
            raise ValueError("raw leaf unusable in subgroup")
        w = sum((basis_w[bit] for bit in range(6) if mask >> bit & 1),
                field.zero()) ** (2**protocol["rotations"][i])
        d = p + fp
        if (d == zero or key(d) != tuple(saved_sum) or
                d[0] != 1 / w or phi(d) != w / (w + 1) or
                encode(phi(d)) != planted["leaf_u"][i] or
                columns[mask] != planted["folded_columns"][i]):
            raise ValueError("diagonal rational identity or saved point failed")
        diagonal.append(d)
    if len(set(planted["folded_columns"])) != 7:
        raise ValueError("control column collision")
    middle = [diagonal[0] + diagonal[1], diagonal[2] + diagonal[3],
              diagonal[4] + diagonal[5]]
    middle.append(middle[0] + middle[1])
    middle.append(middle[3] + middle[2])
    total = middle[4] + diagonal[6]
    if ([encode(phi(p)) for p in middle] != planted["middle_u"] or
            key(total) != tuple(planted["raw_sum"]) or
            key(4 * total) != tuple(planted["target_q"]) or
            R * (4 * total) != zero):
        raise ValueError("Sage chain or target subgroup replay failed")
    result = {"kind": "n41_seven_diagonal_independent_sage_preflight",
              "status": "PASS_EXACT_GEOMETRY_AND_GROUP_CONTROL",
              "curve_id": protocol["curve_id"],
              "actual_factor_base_points_B": len(base_points),
              "effective_folded_columns_K": len(set(columns.values())),
              "source_points_checked": len(source), "raw_control_leaves_checked": 14,
              "diagonal_outputs_checked": 7, "middle_sums_checked": 5,
              "target_q": planted["target_q"],
              "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                "planted": sha(HERE / "planted.json"),
                                "preflight": sha(HERE / "preflight/receipt.json"),
                                "screen": sha(SCREEN),
                                "runtime": sha(HERE / "sage_runtime_info.json"),
                                "audit_script": sha(Path(__file__))}}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "B": len(base_points), "K": result["effective_folded_columns_K"]}))


if __name__ == "__main__":
    main()
