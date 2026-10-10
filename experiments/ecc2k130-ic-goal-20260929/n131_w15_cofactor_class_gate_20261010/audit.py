#!/usr/bin/env sage -python
"""Independent group-law replay of selected W15 class bits."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
ORDER = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    census = json.loads((HERE / "census.json").read_text())
    bits = (HERE / "class_bits.bin").read_bytes()
    assert len(bits) == 32768 and set(bits) == {0, 1}
    assert census["sha256"]["class_bits"] == sha(HERE / "class_bits.bin")
    assert census["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert protocol["sha256"]["support"] == sha(SUPPORT)
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)
    torsion = curve(field.zero(), field.one())
    basis = [field.gen()**i for i in range(1, 16)]
    columns = defaultdict(list)
    for row in SUPPORT.read_text().splitlines():
        mask, column = map(int, row.split())
        columns[column].append(mask)
    masks = sorted(mask for group in columns.values() for mask in group)
    ranked = sorted(masks, key=lambda mask: hashlib.sha256(
        ("cofactor-class-audit:"+str(mask)).encode()).digest())
    chosen = ranked[:256]
    direct = Counter()
    for mask in chosen:
        w = sum((basis[i] for i in range(15) if mask >> i & 1), field.zero())
        assert w != 0 and w.trace() == 0
        points = curve.lift_x(1/w, all=True)
        assert len(points) == 2 and points[0] == -points[1]
        for point in points:
            class_point = ORDER*point
            observed = 0 if class_point == zero else 1 if class_point == torsion else -1
            assert observed == bits[mask], (mask, observed, bits[mask])
            direct[observed] += 1
    assert not [column for column, group in columns.items()
                if len({bits[mask] for mask in group}) > 1]
    assert sum(bits[mask] == 0 for mask in masks) == census["support_class_counts"]["0"]
    assert sum(bits[mask] == 1 for mask in masks) == census["support_class_counts"]["1"]
    receipt = {"status": "PASS_INDEPENDENT_SAGE_W15_COFACTOR_CLASS_REPLAY",
               "sample_rule": "256 smallest SHA-256(cofactor-class-audit:<mask>) on support",
               "masks_checked": len(chosen), "signed_lifts_checked": sum(direct.values()),
               "direct_class_counts": {str(k): v for k, v in sorted(direct.items())},
               "folded_columns_checked": len(columns),
               "sha256": {"script": sha(Path(__file__)),
                          "protocol": sha(HERE / "protocol.json"),
                          "census": sha(HERE / "census.json"),
                          "class_bits": sha(HERE / "class_bits.bin"),
                          "support": sha(SUPPORT)}}
    with (HERE / "audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "masks_checked": receipt["masks_checked"],
                      "signed_lifts_checked": receipt["signed_lifts_checked"]}))


if __name__ == "__main__":
    main()
