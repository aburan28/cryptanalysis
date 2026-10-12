#!/usr/bin/env python3
"""Check generic and exceptional XYZZ accumulation on secp256k1."""

import hashlib
import json
from pathlib import Path
import random
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "prime-j0-secp256k1-native"))
import lazy_tau_screen as curve  # noqa: E402


P = curve.field.P
ORDER = curve.ORDER
SEED = 20261009
SEQUENCES = 64
ADDITIONS_PER_SEQUENCE = 14


class Count:
    def __init__(self):
        self.m = 0
        self.s = 0

    def mul(self, a, b):
        self.m += 1
        return a * b % P

    def sqr(self, a):
        self.s += 1
        return a * a % P


def affine(point):
    if point is None:
        return None
    x, y, zz, zzz = point
    inverse_zzz = pow(zzz, -1, P)
    inverse_z = zz * inverse_zzz % P
    return x * inverse_z * inverse_z % P, y * inverse_zzz % P


def doubled(point):
    if point is None:
        return None, Count()
    x, y, zz, zzz = point
    if y == 0:
        return None, Count()
    ops = Count()
    u = 2 * y % P
    v = ops.sqr(u)
    w = ops.mul(u, v)
    s = ops.mul(x, v)
    m = 3 * ops.sqr(x) % P  # secp256k1 has a=0.
    new_x = (ops.sqr(m) - 2 * s) % P
    new_y = (ops.mul(m, (s - new_x) % P) - ops.mul(w, y)) % P
    new_zz = ops.mul(v, zz)
    new_zzz = ops.mul(w, zzz)
    assert (ops.m, ops.s) == (6, 3)
    return (new_x, new_y, new_zz, new_zzz), ops


def mixed(point, addend):
    if addend is None:
        return point, "identity_addend", Count()
    if point is None:
        return (addend[0], addend[1], 1, 1), "first", Count()
    x, y, zz, zzz = point
    qx, qy = addend
    ops = Count()
    u = ops.mul(qx, zz)
    s = ops.mul(qy, zzz)
    h = (u - x) % P
    r = (s - y) % P
    if h == 0:
        if r == 0:
            result, dbl_ops = doubled(point)
            return result, "equal", dbl_ops
        return None, "inverse", Count()
    hh = ops.sqr(h)
    hhh = ops.mul(h, hh)
    v = ops.mul(x, hh)
    new_x = (ops.sqr(r) - hhh - 2 * v) % P
    new_y = (ops.mul(r, (v - new_x) % P) - ops.mul(y, hhh)) % P
    new_zz = ops.mul(zz, hh)
    new_zzz = ops.mul(zzz, hhh)
    assert (ops.m, ops.s) == (8, 2)
    return (new_x, new_y, new_zz, new_zzz), "generic", ops


def check_step(point, expected, addend):
    next_point, status, ops = mixed(point, addend)
    expected = curve.point_add(expected, addend)
    assert affine(next_point) == expected
    if next_point is not None:
        _, _, zz, zzz = next_point
        assert pow(zz, 3, P) == pow(zzz, 2, P)
    return next_point, expected, status, ops


def main():
    rng = random.Random(SEED)
    digest = hashlib.sha256()
    statuses = {}
    total_m = total_s = 0
    for _ in range(SEQUENCES):
        point = expected = None
        for _ in range(ADDITIONS_PER_SEQUENCE):
            scalar = rng.getrandbits(256) % ORDER
            digest.update(scalar.to_bytes(32, "big"))
            addend = curve.point_multiply(scalar)
            point, expected, status, ops = check_step(point, expected, addend)
            statuses[status] = statuses.get(status, 0) + 1
            total_m += ops.m
            total_s += ops.s
    assert statuses == {"first": SEQUENCES,
                        "generic": SEQUENCES * (ADDITIONS_PER_SEQUENCE - 1)}
    assert (total_m, total_s) == (8 * statuses["generic"], 2 * statuses["generic"])

    generator = curve.GENERATOR
    neg_generator = (generator[0], -generator[1] % P)
    twice = curve.point_add(generator, generator)
    triple = curve.point_add(twice, generator)
    neg_triple = (triple[0], -triple[1] % P)
    affine_generator = (generator[0], generator[1], 1, 1)
    nonaffine, _, status, _ = check_step(affine_generator, generator, twice)
    assert status == "generic" and nonaffine is not None and nonaffine[2] != 1
    exceptional = {}
    cases = (
        (None, None, generator, "first"),
        (affine_generator, generator, generator, "equal"),
        (affine_generator, generator, neg_generator, "inverse"),
        (nonaffine, triple, triple, "equal"),
        (nonaffine, triple, neg_triple, "inverse"),
        (nonaffine, triple, None, "identity_addend"),
    )
    for point, expected, addend, want in cases:
        _, _, status, _ = check_step(point, expected, addend)
        assert status == want
        exceptional[status] = exceptional.get(status, 0) + 1
    assert exceptional == {"first": 1, "equal": 2, "inverse": 2, "identity_addend": 1}

    result = {
        "schema": 1,
        "status": "passed",
        "seed": SEED,
        "sequences": SEQUENCES,
        "additions_per_sequence": ADDITIONS_PER_SEQUENCE,
        "input_sha256": digest.hexdigest(),
        "step_statuses": statuses,
        "exceptional_statuses": exceptional,
        "symbolic_generic_multiplications": total_m,
        "symbolic_generic_squares": total_s,
        "generic_formula": "8M+2S",
        "a_zero_doubling_formula": "6M+3S",
        "curve": "secp256k1",
        "wall_time_ms": None,
        "protocol_sha256": hashlib.sha256((HERE / "PROTOCOL.md").read_bytes()).hexdigest(),
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256((HERE.parent / "prime-j0-secp256k1-native/lazy_tau_screen.py").read_bytes()).hexdigest(),
    }
    output = HERE / "xyzz-formula-result.json"
    if output.exists():
        raise SystemExit("result exists; refusing overwrite")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "sequences", "step_statuses", "exceptional_statuses")}, sort_keys=True))


if __name__ == "__main__":
    main()
