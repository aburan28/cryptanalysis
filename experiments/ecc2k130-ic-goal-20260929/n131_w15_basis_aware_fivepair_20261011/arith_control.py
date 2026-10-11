"""Test universal four-atom quartics on the archived N131 W15 relation."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
INPUT = GOAL / "n131_w15_unrestricted_fivepair_public_20261010/input.json"
NORM = GOAL / "n41_quartic_joint_public_20261010/norm_result.json"
N = 131
MODULUS = (1 << N) | (1 << 13) | (1 << 2) | (1 << 1) | 1
MASK = (1 << N) - 1


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mul(a, b):
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a & (1 << N):
            a ^= MODULUS
    return out


def square(a):
    return mul(a, a)


def frob(a, turns):
    for _ in range(turns):
        a = square(a)
    return a


def trace(a):
    value = a
    out = 0
    for _ in range(N):
        out ^= value
        value = square(value)
    assert out in (0, 1)
    return out


def half_trace(a):
    result = 0
    value = a
    for _ in range((N + 1) // 2):
        result ^= value
        value = square(square(value))
    assert square(result) ^ result == a
    return result


def evaluate(terms, values):
    powers = [[1] for _ in values]
    for axis in range(len(values)):
        for _ in range(max(row[axis] for row in terms)):
            powers[axis].append(mul(powers[axis][-1], values[axis]))
    out = 0
    for exponents in terms:
        value = 1
        for axis, exponent in enumerate(exponents):
            value = mul(value, powers[axis][exponent])
        out ^= value
    return out


def source(mask, rotation):
    raw = sum(1 << (bit + 1) for bit in range(15) if mask >> bit & 1)
    return frob(raw, rotation)


def main():
    data = json.loads(INPUT.read_text())
    norm = json.loads(NORM.read_text())
    masks = data["constructed_remaining_masks"]
    middle = data["constructed_remaining_middle_reciprocals"]
    rotations = (13, 26, 39, 52, 65)
    rows = []
    for block in range(2):
        first = 2 * block
        u = [source(mask, rotations[pair])
             for pair in range(first, first + 2)
             for mask in masks[2 * pair:2 * pair + 2]]
        a, b = u[0] ^ u[1], u[2] ^ u[3]
        p, q = mul(u[0], u[1]), mul(u[2], u[3])
        z = middle[5 + block]
        assert trace(z ^ a ^ b) == 0
        w0 = half_trace(z ^ a ^ b)
        values = (a, a ^ b, z, p, q)
        A = evaluate(norm["A_terms"], values)
        B = evaluate(norm["B_terms"], values)
        branches = [w for w in (w0, w0 ^ 1) if A ^ mul(w, B) == 0]
        assert branches, f"block {block} has no quartic branch"
        rows.append({"block": block, "rotations": rotations[first:first + 2],
                     "source_masks": masks[4 * block:4 * block + 4],
                     "a": a, "b": b, "P": p, "Q": q, "z": z,
                     "A": A, "B": B, "branches": branches})
    record = {"status": "PASS_N131_W15_TWO_QUARTIC_CONSTRUCTED_CONTROL",
              "curve_id": data["curve_id"], "candidate_id": None,
              "field_modulus": "t^131+t^13+t^2+t+1",
              "constructed_residual_target_q": data["constructed_residual_target_q"],
              "blocks": rows, "source_sha256": {"arith_control.py": sha(__file__),
                                              "input.json": sha(INPUT),
                                              "norm_result.json": sha(NORM)}}
    (HERE / "arith_control.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": record["status"],
                      "branch_counts": [len(row["branches"]) for row in rows]}))


if __name__ == "__main__":
    main()
