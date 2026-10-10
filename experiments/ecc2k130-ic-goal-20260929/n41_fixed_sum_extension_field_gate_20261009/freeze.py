#!/usr/bin/env python3
"""Freeze a public-target residual and fixed-sum N41 pair controls."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
ROW = GOAL / "n41_two_free_pair_compact_lookup_20261009/public_search_v2.json"
INPUT = GOAL / "n131_w18_four_pairs/native_join/native_input.txt"
RUNTIME = HERE / "sage_runtime_info.json"
N = 41
R = 549756390943
ROTATIONS = (0, 10, 20, 30)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))


def main():
    out = HERE / "protocol.json"
    if out.exists():
        raise FileExistsError(out)
    row = json.loads(ROW.read_text())
    assert row["status"] == "VERIFIED_RAW_ROW" and len(row["row"]) == 8
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    lines = INPUT.read_text().splitlines()
    assert lines[0] == f"1458168294740 1672312028033 {R} 8"
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**N, name="t", modulus=t**N + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    basis = [field(t**i) for i in range(1, 7)]

    def decode(value):
        return field(ring([(int(value) >> i) & 1 for i in range(N)]))

    def point(coords):
        return curve(decode(coords[0]), decode(coords[1]))

    def seed(mask, rotation):
        value = sum((basis[i] for i in range(6) if mask >> i & 1), field.zero())
        for _ in range(rotation):
            value = value**2
        return value

    def half_trace(value):
        result = field.zero()
        for _ in range((N + 1) // 2):
            result += value
            value = value**4
        return result

    def raw_lift(mask, rotation, subgroup):
        h = half_trace(seed(mask, rotation))
        assert h not in (0, 1)
        candidates = curve.lift_x(1 + 1 / h, all=True)
        matches = [value for value in candidates if 4 * value == subgroup]
        assert len(matches) == 1
        return matches[0]

    q = point(row["target"])
    assert R * q == curve(0)
    raw = [raw_lift(int(leaf["mask"]), ROTATIONS[i // 2],
                    point(leaf["point"])) for i, leaf in enumerate(row["row"])]
    raw_sum = sum(raw, curve(0))
    assert 4 * raw_sum == q
    torsion = [curve(0), curve(0, 1), curve(1, 0), curve(1, 1)]
    assert len({tuple(x) for x in torsion}) == 4
    q0 = pow(4, -1, R) * q
    endpoints = [q0 + value for value in torsion]
    assert all(4 * endpoint == q for endpoint in endpoints)
    assert raw_sum in endpoints
    endpoint_index = endpoints.index(raw_sum)
    prefix = sum(raw[:4], curve(0))
    residual = endpoints[endpoint_index] - prefix
    assert residual == sum(raw[4:], curve(0))
    assert residual != curve(0) and residual[0] != 1
    s_positive = [row["row"][2 * i]["mask"] ^ row["row"][2 * i + 1]["mask"]
                  for i in (2, 3)]
    assert all(s_positive)
    positive_outputs = []
    positive_epsilons = []
    for pair in (2, 3):
        left_mask = row["row"][2 * pair]["mask"]
        s = seed(s_positive[pair - 2], ROTATIONS[pair])
        a = seed(left_mask, ROTATIONS[pair])
        p = a*a + s*a
        z_point = raw[2 * pair] + raw[2 * pair + 1]
        assert z_point != curve(0) and z_point[0] != 1
        z = 1 / (z_point[0] + 1)
        epsilon = z*z + half_trace(s)**2 + (z*z + z)*p
        assert epsilon in (0, 1)
        positive_outputs.append(encode(z))
        positive_epsilons.append(int(epsilon))
    z0, z1 = [decode(value) for value in positive_outputs]
    c = 1 / (residual[0] + 1)
    assert (z0*z0 + z0)*(z1*z1 + z1)*(c*c + c) + (z0 + z1 + c)**2 == 0

    # Exact raw pair domains establish a negative control independently of F4.
    pos = 1
    slots = []
    for slot in range(8):
        count = int(lines[pos]); pos += 1
        values = [list(map(int, lines[pos + j].split())) for j in range(count)]
        pos += count
        slots.append(values)
    assert pos == len(lines)
    pair_domains = []
    for pair in (2, 3):
        rotation = ROTATIONS[pair]
        points = []
        for x, y, column, mask, branch, sign in slots[2 * pair]:
            assert branch == 0
            points.append((mask, column, raw_lift(mask, rotation, point((x, y)))))
        assert len(points) == 64
        groups = {}
        for i, (a, ca, pa) in enumerate(points):
            for b, cb, pb in points[i + 1:]:
                if ca != cb:
                    groups.setdefault(a ^ b, set()).add(pa + pb)
        pair_domains.append(groups)
    assert all(s_positive[i] in pair_domains[i] for i in range(2))
    assert any(residual - value in pair_domains[1][s_positive[1]]
               for value in pair_domains[0][s_positive[0]])
    negative = next((s0, s1) for s0 in sorted(pair_domains[0])
                    for s1 in sorted(pair_domains[1])
                    if (s0, s1) != tuple(s_positive)
                    and not any(residual - value in pair_domains[1][s1]
                                for value in pair_domains[0][s0]))

    record = {
        "status": "FROZEN", "proposal_id": "Q20261009192700",
        "candidate_id": None, "run_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "target_count": 1, "target_q": row["target"],
        "field_modulus_exponents": [0, 3, 41], "subgroup_order": R,
        "rotations": list(ROTATIONS),
        "raw_endpoint_index": endpoint_index,
        "raw_endpoint": [encode(raw_sum[0]), encode(raw_sum[1])],
        "prefix_subgroup_points": [leaf["point"] for leaf in row["row"][:4]],
        "prefix_masks": [leaf["mask"] for leaf in row["row"][:4]],
        "residual": [encode(residual[0]), encode(residual[1])],
        "residual_phi": encode(1 / (residual[0] + 1)),
        "positive_sum_masks": s_positive,
        "positive_outputs": positive_outputs,
        "positive_epsilons": positive_epsilons,
        "negative_sum_masks": list(negative),
        "positive_pair_leaf_masks": [leaf["mask"] for leaf in row["row"][4:]],
        "exact_pair_domain_sizes": [{str(s): len(v) for s, v in d.items()}
                                    for d in pair_domains],
        "limits": {"per_case_seconds": 45, "combined_rss_bytes": 4 * 1024**3,
                   "workers": 1},
        "input_law": "frozen public Q; verified four-leaf prefix and fixed seed sums form a target-coupled two-free-pair method control",
        "sha256": {"freeze": sha(__file__), "solver": sha(HERE / "solve.py"),
                   "supervisor": sha(HERE / "run_cases.py"),
                   "audit": sha(HERE / "audit.py"), "row": sha(ROW),
                   "input": sha(INPUT), "runtime": sha(RUNTIME)},
    }
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "endpoint_index": endpoint_index,
                      "positive": s_positive, "negative": negative,
                      "residual_phi": record["residual_phi"]}))


if __name__ == "__main__":
    main()
