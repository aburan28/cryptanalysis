#!/usr/bin/env sage -python
"""Specialize the universal same-seed four-atom resultant to an affine plane."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    source = PARENT / "resultant_terms.json"
    assert protocol["source_sha256"]["script"] == digest(__file__)
    assert protocol["source_sha256"]["universal_resultant"] == digest(source)
    prior = json.loads(source.read_text())
    ring = PolynomialRing(GF(2), names=("s", "c", "p", "z"))
    s, c, p, z = ring.gens()
    delta = c*c + s*c
    q = p + delta
    h = ring.zero()
    for es, ep, eq, ez in prior["terms_s_p_q_z"]:
        h += s**es * p**ep * q**eq * z**ez
    assert h != 0 and h.degree(p) <= 16
    assert h(p=q) == h
    terms = sorted([list(map(int, exponent)) for exponent in h.dict()])
    out = {
        "status": "PASS_AFFINE_PLANE_RESULTANT_SPECIALIZATION",
        "relation": "q=p+c^2+s*c; p=w^2+s*w; q=(w+c)^2+s*(w+c)",
        "term_count": len(terms),
        "degrees": {name: int(h.degree(var)) for name, var in (
            ("s", s), ("c", c), ("p", p), ("z", z))},
        "symmetric_under_pair_translation": True,
        "terms_s_c_p_z": terms,
        "source_sha256": {"script": digest(__file__),
                          "protocol": digest(HERE / "protocol.json"),
                          "universal_resultant": digest(source)},
    }
    with (HERE / "resultant.json").open("x") as f:
        json.dump(out, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"status": out["status"], "term_count": len(terms),
                      "degrees": out["degrees"]}))


if __name__ == "__main__":
    main()
