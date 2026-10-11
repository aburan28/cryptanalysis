#!/usr/bin/env sage -python
"""Freeze a secondary N41 ordinary-point panel independently of the solver."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
R = 549756390943
COUNT = 16
SEED_PREFIX = b"n41-affine-plane-ordinary-yield-panel-20261010-v1/"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "fixture_protocol.json").read_text())
    assert protocol["generator_sha256"] == sha256(__file__)
    assert protocol["sage_runtime_sha256"] == sha256(HERE / "sage_runtime_info.json")
    assert protocol["count"] == COUNT

    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(poly([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    generator = curve(decode(2056947637384), decode(1635505394702))
    assert R * generator == curve(0)
    previous = [107983884862, 1122076153229]
    public, private = [], []
    seen = {tuple(previous)}
    for index in range(COUNT):
        label = (SEED_PREFIX + str(index).encode()).decode()
        scalar = int.from_bytes(hashlib.sha256(label.encode()).digest(), "big") % R
        assert scalar != 0
        point = scalar * generator
        target = [encode(point[0]), encode(point[1])]
        assert tuple(target) not in seen
        assert R * point == curve(0)
        seen.add(tuple(target))
        public.append({"index": index, "target": target})
        private.append({"index": index, "seed_label": label, "scalar": scalar,
                        "target": target})

    result = {"curve_id": "EC1N41Ckb1h023d9a38bbf7", "target_count": COUNT,
              "input_law": "SHA-256-derived nonzero scalars; only points enter solver",
              "targets": public}
    fixture = {"curve_id": result["curve_id"], "generator": [2056947637384,1635505394702],
               "subgroup_order": R, "targets": private,
               "source_sha256": {"generator": sha256(__file__),
                                 "protocol": sha256(HERE / "fixture_protocol.json"),
                                 "runtime": sha256(HERE / "sage_runtime_info.json")}}
    for name, value in (("public_targets.json", result), ("private_fixture.json", fixture)):
        with (HERE / name).open("x") as out:
            json.dump(value, out, indent=2, sort_keys=True)
            out.write("\n")
    print(json.dumps({"status": "PASS_PANEL_FIXTURE", "target_count": COUNT,
                      "public_sha256": sha256(HERE / "public_targets.json")}))


if __name__ == "__main__":
    main()
