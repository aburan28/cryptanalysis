"""Sound linear relaxation of two partial pair outputs and their public S3 link."""

import hashlib
import json
import random
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "n41_full_firsthalf_exact_20261011"
N = 41
MASK = (1 << N) - 1
MOD_LOW = (1 << 3) | 1
WIDTHS = (0, 2, 4, 6, 8, 10, 12)
SAMPLE_SEED = 202610111942
CONTROL_COUNT = 128


def mul(a, b):
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a >> N:
            a = (a & MASK) ^ MOD_LOW
    return out


def sq(a):
    return mul(a, a)


def inv(a):
    assert a
    u, v = a, (1 << N) | MOD_LOW
    g, h = 1, 0
    while u != 1:
        j = u.bit_length() - v.bit_length()
        if j < 0:
            u, v = v, u
            g, h = h, g
            j = -j
        u ^= v << j
        g ^= h << j
    while g.bit_length() > N:
        g ^= ((1 << N) | MOD_LOW) << (g.bit_length() - N - 1)
    return g


def add(p, q):
    if p is None:
        return q
    if q is None:
        return p
    x, y = p
    u, v = q
    if x == u:
        if y != v or x == 0:
            return None
        lam = x ^ mul(y, inv(x))
        nx = sq(lam) ^ lam
        return (nx, sq(x) ^ mul(lam ^ 1, nx))
    lam = mul(y ^ v, inv(x ^ u))
    nx = sq(lam) ^ lam ^ x ^ u
    return (nx, mul(lam, x ^ nx) ^ nx ^ y)


def frob(a, steps):
    for _ in range(steps):
        a = sq(a)
    return a


def trace(a):
    out = 0
    for _ in range(N):
        out ^= a
        a = sq(a)
    assert out in (0, 1)
    return out


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_pairs():
    lines = (SOURCE / "exact_input.txt").read_text().splitlines()
    count = int(lines[0])
    assert count == 1712
    target_x, target_y = map(int, lines[1].split()[1:])
    cursor = 1 + count
    blocks = []
    for rotation in (20, 30):
        assert lines[cursor] == f"{rotation} 64"
        cursor += 1
        rows = []
        for line in lines[cursor:cursor+64]:
            x, y, column, mask, branch, sign = map(int, line.split())
            raw = (x, y)
            d = add(raw, (sq(x), sq(y)))
            assert d is not None and d[0]
            w = frob(mask << 1, rotation)
            assert inv(d[0]) == w
            rows.append((d, column, mask, w))
        blocks.append(rows)
        cursor += 64
    assert cursor == len(lines)
    pairs = []
    for rows, rotation in zip(blocks, (20, 30)):
        domain = []
        for i in range(64):
            for j in range(i+1, 64):
                a, b = rows[i], rows[j]
                if a[1] == b[1]:
                    continue
                group = add(a[0], b[0])
                assert group is not None and group[0]
                c = inv(group[0])
                s = a[3] ^ b[3]
                p = mul(a[3], b[3])
                assert (sq(c) ^ sq(s) ^ mul(p, c) ^ mul(sq(p), sq(c))) == 0
                domain.append({"ids": [i, j], "columns": [a[1], b[1]],
                               "seed_mask": a[2] ^ b[2], "rotation": rotation,
                               "c": c, "s": s, "p": p,
                               "point": list(group)})
        assert len(domain) == 1956
        pairs.append(domain)
    return (target_x, target_y), pairs


def image_basis(seed_mask, rotation):
    s = frob(seed_mask << 1, rotation)
    generators = []
    pivots = {}
    for bit in range(6):
        a = frob(1 << (bit+1), rotation)
        value = sq(a) ^ mul(s, a)
        reduced = value
        for pivot in sorted(pivots, reverse=True):
            if (reduced >> pivot) & 1:
                reduced ^= pivots[pivot]
        if reduced:
            pivots[reduced.bit_length()-1] = reduced
            generators.append(value)
    assert len(generators) == 5
    return generators


def consistent(columns, rhs):
    pivots = {}
    rank = 0
    for value in columns:
        while value:
            bit = value.bit_length()-1
            if bit in pivots:
                value ^= pivots[bit]
            else:
                pivots[bit] = value
                rank += 1
                break
    value = rhs
    while value:
        bit = value.bit_length()-1
        if bit not in pivots:
            return False, rank
        value ^= pivots[bit]
    return True, rank


def pair_columns(c0, s, product_basis, width):
    constant = sq(c0) ^ sq(s)
    delta = [1 << i for i in range(width)]
    linear_delta = [sq(e) for e in delta]
    product = [mul(b, c0) ^ mul(sq(b), sq(c0)) for b in product_basis]
    cross = [mul(b, e) ^ mul(sq(b), sq(e))
             for e in delta for b in product_basis]
    return constant, linear_delta, product, cross


def joint_consistency(left, right, target_z, width):
    mask = (1 << width)-1
    c, d = left["c"] & ~mask, right["c"] & ~mask
    lc = pair_columns(c, left["s"],
                      image_basis(left["seed_mask"], left["rotation"]), width)
    rc = pair_columns(d, right["s"],
                      image_basis(right["seed_mask"], right["rotation"]), width)
    left_local = consistent(lc[1]+lc[2]+lc[3], lc[0])
    right_local = consistent(rc[1]+rc[2]+rc[3], rc[0])
    z = target_z
    cd = mul(c, d)
    third_constant = sq(z) ^ mul(sq(cd), sq(z)) ^ mul(cd, z) ^ sq(c) ^ sq(d)
    dleft, dright = [1 << i for i in range(width)], [1 << i for i in range(width)]

    def third_linear(e, other):
        product = mul(e, other)
        return sq(e) ^ mul(sq(product), sq(z)) ^ mul(product, z)

    def third_cross(e, f):
        product = mul(e, f)
        return mul(sq(product), sq(z)) ^ mul(product, z)

    columns = []
    columns.extend(v | (third_linear(e, d) << (2*N))
                   for v, e in zip(lc[1], dleft))
    columns.extend((v << N) | (third_linear(e, c) << (2*N))
                   for v, e in zip(rc[1], dright))
    columns.extend(lc[2])
    columns.extend(rc_v << N for rc_v in rc[2])
    columns.extend(lc[3])
    columns.extend(rc_v << N for rc_v in rc[3])
    columns.extend(third_cross(e, f) << (2*N)
                   for e in dleft for f in dright)
    rhs = lc[0] | (rc[0] << N) | (third_constant << (2*N))
    joint = consistent(columns, rhs)
    return {"left_local": left_local[0], "right_local": right_local[0],
            "joint": joint[0], "rank": joint[1],
            "variables": len(columns)}


def freeze():
    target, pairs = source_pairs()
    receipt = json.loads((SOURCE / "receipt.json").read_text())
    positive = receipt["queries"][0]
    ids = []
    for block, coordinates in zip(pairs, (positive["left_pair_point"],
                                            positive["right_pair_point"])):
        matches = [i for i, item in enumerate(block) if item["point"] == coordinates]
        assert len(matches) == 1
        ids.append(matches[0])
    rng = random.Random(SAMPLE_SEED)
    selected = [list((rng.randrange(1956), rng.randrange(1956)))
                for _ in range(CONTROL_COUNT)]
    panel = {"status": "FROZEN_EXACT_PAIR_PARTIAL_OUTPUT_PANEL",
             "candidate_id": None, "target": list(target),
             "positive_ids": ids, "control_ids": selected,
             "input_law": "uniform independent exact pair IDs with replacement, fixed positive target",
             "seed": SAMPLE_SEED, "widths": list(WIDTHS)}
    (HERE / "panel.json").write_text(json.dumps(panel, indent=2, sort_keys=True)+"\n")
    protocol = {"status": "FROZEN_JOINT_LINEAR_N41_PROTOCOL",
                "candidate_id": None,
                "limits": {"workers": 1, "seconds": 120, "rss_bytes": 4294967296},
                "sha256": {"run": sha(__file__),
                           "panel": sha(HERE / "panel.json"),
                           "input": sha(SOURCE / "exact_input.txt"),
                           "exact_receipt": sha(SOURCE / "receipt.json")}}
    (HERE / "protocol.json").write_text(json.dumps(protocol, indent=2, sort_keys=True)+"\n")
    print(panel["status"], "positive", ids, "controls", len(selected))


def evaluate():
    protocol = json.loads((HERE / "protocol.json").read_text())
    panel = json.loads((HERE / "panel.json").read_text())
    assert protocol["sha256"]["run"] == sha(__file__)
    assert protocol["sha256"]["panel"] == sha(HERE / "panel.json")
    assert protocol["sha256"]["input"] == sha(SOURCE / "exact_input.txt")
    assert protocol["sha256"]["exact_receipt"] == sha(SOURCE / "receipt.json")
    target, pairs = source_pairs()
    assert list(target) == panel["target"]
    z = inv(target[0])
    assert trace(z) == 0
    cases = [("positive", panel["positive_ids"])]
    cases += [(f"control_{i}", ids) for i, ids in enumerate(panel["control_ids"])]
    rows = []
    start = time.monotonic_ns()
    for label, ids in cases:
        left, right = pairs[0][ids[0]], pairs[1][ids[1]]
        group_match = add(tuple(left["point"]), tuple(right["point"])) == target
        assert group_match if label == "positive" else True
        decisions = {str(width): joint_consistency(left, right, z, width)
                     for width in WIDTHS}
        if label == "positive":
            assert all(item["joint"] for item in decisions.values())
        assert all(item["left_local"] and item["right_local"]
                   for item in decisions.values())
        rows.append({"label": label, "pair_ids": ids,
                     "seed_masks": [left["seed_mask"], right["seed_mask"]],
                     "pair_coordinates": [left["c"], right["c"]],
                     "group_match": group_match, "decisions": decisions})
        if time.monotonic_ns()-start > 120_000_000_000:
            raise TimeoutError("frozen 120-second cap")
    elapsed = time.monotonic_ns()-start
    summary = {}
    for width in WIDTHS:
        name = str(width)
        summary[name] = {"controls_passing_joint": sum(row["decisions"][name]["joint"]
                                                       for row in rows[1:]),
                         "controls_passing_both_local": sum(
                             row["decisions"][name]["left_local"] and
                             row["decisions"][name]["right_local"]
                             for row in rows[1:]),
                         "positive_passing": rows[0]["decisions"][name]["joint"]}
    output = {"status": "COMPLETE_N41_JOINT_PARTIAL_LINEAR_PANEL",
              "candidate_id": None, "target": list(target),
              "controls": CONTROL_COUNT, "elapsed_ns": elapsed,
              "pair_domain_sizes": [len(v) for v in pairs],
              "summary": summary, "rows": rows,
              "protocol_sha256": sha(HERE / "protocol.json")}
    (HERE / "result.json").write_text(json.dumps(output, indent=2, sort_keys=True)+"\n")
    print(output["status"], "elapsed", elapsed/1e9)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "evaluate"):
        raise SystemExit("usage: run.py freeze|evaluate")
    (freeze if sys.argv[1] == "freeze" else evaluate)()
