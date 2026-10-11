#!/usr/bin/env sage -python
"""Prove the four-product identity and compare link circuits on exact field inputs."""

import hashlib
import json
import random
import sys
from pathlib import Path

from sage.all import GF, PolynomialRing


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BASE))
import fixed_pair_circuit as pair  # noqa: E402
import fourmul  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_link(builder):
    prog = pair.new_program()
    one = prog.addInput("one", 0)
    vectors = [[prog.addInput(name, bit) for bit in range(pair.N)]
               for name in ("u", "v", "w")]
    roots = builder(prog, *vectors, one, cutoff=3)
    return prog, roots


def bits(values, name, value):
    values.update({(name, bit): (value >> bit) & 1 for bit in range(pair.N)})


def main():
    protocol_path = HERE / "link_equivalence_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "fourmul": HERE / "fourmul.py",
             "fourmul_result": HERE / "result.json",
             "baseline_circuit": BASE / "fixed_pair_circuit.py",
             "sage_runtime": BASE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    ring = PolynomialRing(GF(2), names=("u", "v", "w"))
    u, v, w = ring.gens()
    symmetric_old = u*v + u*w + v*w
    symmetric_new = u*v + w*(u+v)
    assert symmetric_old == symmetric_new
    triple = u*v*w
    first = u+v+w
    assert ((triple+first)**2 + triple*(symmetric_old+first+1) ==
            (triple+first)**2 + triple*(symmetric_new+first+1))

    old, old_roots = make_link(pair.reciprocal_s3_ir)
    new, new_roots = make_link(fourmul.reciprocal_s3_fourmul_ir)
    assert len(old_roots) == len(new_roots) == pair.N
    samples = [(0, 0, 0), (1, 1, 1)]
    generator = random.Random(20261010)
    samples += [tuple(generator.getrandbits(pair.N) for _ in range(3))
                for _ in range(16)]
    for ua, va, wa in samples:
        values = {("one", 0): 1}
        bits(values, "u", ua)
        bits(values, "v", va)
        bits(values, "w", wa)
        old_value = sum(value << bit for bit, value in
                        enumerate(old.evaluate(values, old_roots)))
        new_value = sum(value << bit for bit, value in
                        enumerate(new.evaluate(values, new_roots)))
        uv = pair.gf_mul(ua, va)
        uw = pair.gf_mul(ua, wa)
        vw = pair.gf_mul(va, wa)
        t = pair.gf_mul(uv, wa)
        s1 = ua ^ va ^ wa
        s2 = uv ^ uw ^ vw
        direct = pair.gf_square(t ^ s1) ^ pair.gf_mul(t, s2 ^ s1 ^ 1)
        assert old_value == new_value == direct
    result = {"status": "PASS_SYMBOLIC_AND_18_EXACT_N131_LINK_INPUTS",
              "symbolic_identity": "uv+uw+vw=uv+w(u+v)",
              "field_input_count": len(samples),
              "old_link_live_ops": old.opCount(old_roots),
              "new_link_live_ops": new.opCount(new_roots),
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "link_equivalence_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "old_link_live_ops": result["old_link_live_ops"],
                      "new_link_live_ops": result["new_link_live_ops"]}))


if __name__ == "__main__":
    main()
