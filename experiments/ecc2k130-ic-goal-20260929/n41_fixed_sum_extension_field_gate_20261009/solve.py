#!/usr/bin/env python3
"""Extension-field Groebner gate for two fixed-sum N41 pair blocks."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
N = 41


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(field, binary_ring, value):
    return field(binary_ring([(int(value) >> i) & 1 for i in range(N)]))


def half_trace(value):
    field = value.parent()
    result = field.zero()
    for _ in range((N + 1) // 2):
        result += value
        value = value**4
    return result


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("positive", "negative"):
        raise SystemExit("usage: ./sage -python solve.py positive|negative")
    case = sys.argv[1]
    out = HERE / case / "result.json"
    if out.exists():
        raise FileExistsError(out)
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN"
    assert protocol["sha256"]["solver"] == sha(__file__)
    sums = protocol[f"{case}_sum_masks"]
    binary_ring = PolynomialRing(GF(2), "t")
    t = binary_ring.gen()
    field = GF(2**N, name="t", modulus=t**N + t**3 + 1)
    names = [f"a{pair}_{i}" for pair in range(2) for i in range(6)]
    names += ["epsilon0", "epsilon1", "z0", "z1"]
    ring = PolynomialRing(field, names=names, order="degrevlex")
    gen = dict(zip(names, ring.gens()))
    equations = []
    pair_variables = []
    for pair in range(2):
        rotation = protocol["rotations"][pair + 2]
        basis = [field(t**i) for i in range(1, 7)]
        for _ in range(rotation):
            basis = [value**2 for value in basis]
        s = sum((basis[i] for i in range(6) if sums[pair] >> i & 1),
                field.zero())
        assert s and half_trace(s)**2 + half_trace(s) == s
        a_bits = [gen[f"a{pair}_{i}"] for i in range(6)]
        a = sum((ring(basis[i]) * a_bits[i] for i in range(6)), ring.zero())
        p = a*a + ring(s)*a
        z = gen[f"z{pair}"]
        epsilon = gen[f"epsilon{pair}"]
        equations.append(z*z + ring(half_trace(s)**2) + epsilon +
                         (z*z + z)*p)
        equations.extend(bit*bit + bit for bit in a_bits + [epsilon])
        pair_variables.append(z)
    z0, z1 = pair_variables
    residual_phi = decode(field, binary_ring, protocol["residual_phi"])
    equations.append((z0*z0 + z0)*(z1*z1 + z1)*
                     ring(residual_phi**2 + residual_phi) +
                     (z0 + z1 + ring(residual_phi))**2)
    assert len(equations) == 17 and len(ring.gens()) == 16
    print(json.dumps({"status": "START_GROEBNER", "case": case,
                      "variables": len(ring.gens()), "equations": len(equations),
                      "max_input_degree": int(max(q.total_degree() for q in equations))}),
          flush=True)
    started = time.monotonic_ns()
    basis = ring.ideal(equations).groebner_basis(algorithm="singular:slimgb")
    groebner_ns = time.monotonic_ns() - started
    status = "PROVED_UNIT_IDEAL" if len(basis) == 1 and basis[0] == 1 else "NONUNIT_IDEAL"
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record = {
        "status": status, "case": case, "sum_masks": sums,
        "variables": len(ring.gens()), "equations": len(equations),
        "max_input_degree": int(max(q.total_degree() for q in equations)),
        "groebner_ns": groebner_ns,
        "basis_length": len(basis),
        "basis_max_total_degree": int(max(q.total_degree() for q in basis)),
        "peak_self_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
        "protocol_sha256": sha(HERE / "protocol.json"),
    }
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "case": case,
                      "basis_length": len(basis), "groebner_ns": groebner_ns}),
          flush=True)


if __name__ == "__main__":
    main()
