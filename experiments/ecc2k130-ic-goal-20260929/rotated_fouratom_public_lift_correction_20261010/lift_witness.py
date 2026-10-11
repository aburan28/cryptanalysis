"""Locate the verified N41 public relation in the corrected raw-lift set."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCREEN = ROOT / "n41_n131_diagonal_atom_20261010" / "screen.json"
HIT = ROOT / "n41_seed_partition_indexless_20261010" / "hit.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "lift_protocol.json").read_text())
    for label, (path, expected) in protocol["source_sha256"].items():
        assert sha(Path(path)) == expected, label
    corrected = json.loads((HERE / "result.json").read_text())["n41"]
    screen = json.loads(SCREEN.read_text())
    hit = json.loads(HIT.read_text())
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def point(values):
        return curve(decode(values[0]), decode(values[1]))

    def field_mask(mask):
        return sum((field.gen()**(i+1) for i in range(6) if mask >> i & 1), field.zero())

    raw_by_mask = {row["mask"]: row for row in screen["raw_audit"]}
    raw_points = []
    for block, rotation in enumerate((0, 5, 10, 15, 20, 25)):
        for local in range(2):
            index = 2 * block + local
            mask, sign = hit["masks"][index], hit["signs"][index]
            slots = [row for row in screen["slots"][block]
                     if row["mask"] == mask and row["sign"] == sign]
            assert len(slots) == 1
            leaf = point(slots[0]["point"])
            raw = point(raw_by_mask[mask]["raw_pair_point"])
            assert raw[0] == 1 / field_mask(mask)
            for _ in range(rotation):
                raw = curve(raw[0]**2, raw[1]**2)
            if 4 * raw != leaf:
                raw = -raw
            assert 4 * raw == leaf
            raw_points.append(raw)
    raw_total = sum(raw_points, curve(0))
    public = point(corrected["public_target"])
    assert 4 * raw_total == public
    coordinates = [encode(raw_total[0]), encode(raw_total[1])]
    matching = [row for row in corrected["preimages"] if row["point"] == coordinates]
    assert len(matching) == 1
    blocks = []
    for start in (0, 4, 8):
        total = sum(raw_points[start:start+4], curve(0))
        assert total != curve(0) and total[0] != 0
        blocks.append({"source_slots": list(range(start, start+4)),
                       "point": [encode(total[0]), encode(total[1])],
                       "z_h_reciprocal_x": encode(1/total[0]),
                       "trace_z_h": int((1/total[0]).trace())})
    result = {"status": "PASS_N41_PUBLIC_RELATION_CORRECTED_RAW_LIFT",
              "protocol_sha256": sha(HERE / "lift_protocol.json"),
              "raw_sum": coordinates, "raw_preimage_index": matching[0]["index"],
              "raw_target_z_h": matching[0]["z_h_reciprocal_x"],
              "masks": hit["masks"], "signs": hit["signs"],
              "seed_sums": hit["seed_sums"], "four_atom_blocks": blocks}
    with (HERE / "lift_result.json").open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps({"status": result["status"], "raw_preimage_index": result["raw_preimage_index"],
                      "block_traces": [row["trace_z_h"] for row in blocks]}, sort_keys=True))


if __name__ == "__main__":
    main()
