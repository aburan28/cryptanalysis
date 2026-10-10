#!/usr/bin/env python3
"""Independent Sage group and field replay of the fixed-sum controls."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
ROW = GOAL / "n41_two_free_pair_compact_lookup_20261009/public_search_v2.json"
INPUT = GOAL / "n131_w18_four_pairs/native_join/native_input.txt"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert protocol["status"] == "FROZEN" and runtime["status"] == "verified"
    files = {"freeze": HERE / "freeze.py", "solver": HERE / "solve.py",
             "audit": HERE / "audit.py", "supervisor": HERE / "run_cases.py",
             "row": ROW, "input": INPUT,
             "runtime": HERE / "sage_runtime_info.json"}
    assert all(sha(path) == protocol["sha256"][name]
               for name, path in files.items())
    witness = json.loads(ROW.read_text())
    binary = PolynomialRing(GF(2), "u")
    u = binary.gen()
    field = GF(2**41, name="u", modulus=u**41 + u**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(binary([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))

    def point(coords):
        return curve(decode(coords[0]), decode(coords[1]))

    def half_trace(value):
        result = field.zero()
        for _ in range(21):
            result += value
            value = value**4
        return result

    def seed(mask, rotation):
        value = sum((field(u**(i + 1)) for i in range(6) if mask >> i & 1),
                    field.zero())
        for _ in range(rotation):
            value = value**2
        return value

    def raw_lift(mask, rotation, subgroup):
        h = half_trace(seed(mask, rotation))
        matches = [value for value in curve.lift_x(1 + 1 / h, all=True)
                   if 4 * value == subgroup]
        assert len(matches) == 1
        return matches[0]

    q = point(protocol["target_q"])
    assert q == point(witness["target"])
    assert protocol["subgroup_order"] * q == curve(0)
    rotations = protocol["rotations"]
    row = witness["row"]
    raw = [raw_lift(leaf["mask"], rotations[i // 2], point(leaf["point"]))
           for i, leaf in enumerate(row)]
    assert 4 * sum(raw, curve(0)) == q
    q0 = pow(4, -1, protocol["subgroup_order"]) * q
    endpoints = [q0 + t for t in (curve(0), curve(0, 1),
                                  curve(1, 0), curve(1, 1))]
    endpoint = endpoints[protocol["raw_endpoint_index"]]
    assert endpoint == sum(raw, curve(0))
    residual = endpoint - sum(raw[:4], curve(0))
    assert [encode(residual[0]), encode(residual[1])] == protocol["residual"]
    c = 1 / (residual[0] + 1)
    assert encode(c) == protocol["residual_phi"]

    outputs = []
    epsilons = []
    for pair in (2, 3):
        m0, m1 = row[2 * pair]["mask"], row[2 * pair + 1]["mask"]
        s = seed(m0 ^ m1, rotations[pair])
        assert m0 ^ m1 == protocol["positive_sum_masks"][pair - 2]
        a = seed(m0, rotations[pair])
        p = a*a + s*a
        point_sum = raw[2 * pair] + raw[2 * pair + 1]
        z = 1 / (point_sum[0] + 1)
        e = z*z + half_trace(s)**2 + (z*z + z)*p
        assert e in (0, 1)
        outputs.append(z)
        epsilons.append(int(e))
    z0, z1 = outputs
    assert (z0*z0 + z0)*(z1*z1 + z1)*(c*c + c) + (z0 + z1 + c)**2 == 0
    assert [encode(z0), encode(z1)] == protocol["positive_outputs"]
    assert epsilons == protocol["positive_epsilons"]

    lines = INPUT.read_text().splitlines()
    pos = 1
    slots = []
    for slot in range(8):
        count = int(lines[pos]); pos += 1
        values = [list(map(int, lines[pos + j].split())) for j in range(count)]
        pos += count
        slots.append(values)
    assert pos == len(lines)
    domains = []
    for pair in (2, 3):
        leaves = [(mask, col, raw_lift(mask, rotations[pair], point((x, y))))
                  for x, y, col, mask, branch, sign in slots[2 * pair]]
        groups = {}
        for i, (a, ca, pa) in enumerate(leaves):
            for b, cb, pb in leaves[i + 1:]:
                if ca != cb:
                    groups.setdefault(a ^ b, set()).add(pa + pb)
        assert {str(s): len(v) for s, v in groups.items()} == \
            protocol["exact_pair_domain_sizes"][pair - 2]
        domains.append(groups)
    negative = protocol["negative_sum_masks"]
    assert not any(residual - value in domains[1][negative[1]]
                   for value in domains[0][negative[0]])
    cases = {}
    for case in ("positive", "negative"):
        directory = HERE / case
        terminal = json.loads((directory / "terminal.json").read_text())
        assert terminal["case"] == case
        assert terminal["protocol_sha256"] == sha(HERE / "protocol.json")
        assert terminal["stdout_sha256"] == sha(directory / "stdout.txt")
        assert terminal["stderr_sha256"] == sha(directory / "stderr.txt")
        result = directory / "result.json"
        if result.exists():
            solver = json.loads(result.read_text())
            assert terminal["result_sha256"] == sha(result)
            assert solver["status"] == terminal["status"]
            assert solver["protocol_sha256"] == sha(HERE / "protocol.json")
            assert solver["variables"] == 16 and solver["equations"] == 17
            assert solver["groebner_ns"] <= terminal["launcher_wall_ns"]
        else:
            assert terminal["status"] in ("WALL_CAP", "MEMORY_GUARD", "PRODUCER_FAILURE")
        assert terminal["peak_sampled_family_rss_bytes"] < 4 * 1024**3
        cases[case] = terminal["status"]
    assert cases["positive"] != "PROVED_UNIT_IDEAL"
    receipt = {
        "status": "PASS_INDEPENDENT_SAGE_REPLAY",
        "public_target": protocol["target_q"],
        "positive_pair_outputs": [encode(value) for value in outputs],
        "positive_epsilons": epsilons,
        "negative_exact_domain_empty": True,
        "case_statuses": cases,
        "protocol_sha256": sha(HERE / "protocol.json"),
    }
    (HERE / "audit.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
