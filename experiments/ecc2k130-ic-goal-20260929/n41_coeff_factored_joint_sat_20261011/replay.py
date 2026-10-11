"""Independently lift an N41 Boolean model to the raw curve and subgroup."""

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INPUT = ROOT / "n41_coupled_sixpair_full_ic_20261010" / "heldout_input.txt"
LIFTS = ROOT / "rotated_fouratom_public_lift_correction_20261010" / "result.json"
MODEL = HERE / "model_decoded.json"


class Field:
    n = 41
    modulus = (1 << 41) | (1 << 3) | 1

    def mul(self, a, b):
        out = 0
        while b:
            if b & 1:
                out ^= a
            b >>= 1
            a <<= 1
            if a >> self.n:
                a ^= self.modulus
        return out

    def square(self, a):
        return self.mul(a, a)

    def inv(self, a):
        assert a
        exponent = (1 << self.n) - 2
        out = 1
        while exponent:
            if exponent & 1:
                out = self.mul(out, a)
            a = self.square(a)
            exponent >>= 1
        return out

    def halftrace(self, a):
        out = 0
        term = a
        for _ in range((self.n + 1) // 2):
            out ^= term
            term = self.square(self.square(term))
        assert self.square(out) ^ out == a
        return out


def add(field, left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2:
        if y1 ^ y2 == x1:
            return None
        assert left == right and x1
        slope = x1 ^ field.mul(y1, field.inv(x1))
        x3 = field.square(slope) ^ slope
        y3 = field.square(x1) ^ field.mul(slope ^ 1, x3)
    else:
        slope = field.mul(y1 ^ y2, field.inv(x1 ^ x2))
        x3 = field.square(slope) ^ slope ^ x1 ^ x2
        y3 = field.mul(slope, x1 ^ x3) ^ x3 ^ y1
    return x3, y3


def on_curve(field, point):
    x, y = point
    return field.square(y) ^ field.mul(x, y) == field.mul(field.square(x), x) ^ 1


def times4(field, point):
    doubled = add(field, point, point)
    return add(field, doubled, doubled)


def source(field):
    lines = INPUT.read_text().splitlines()
    qx, qy, order, blocks = map(int, lines[0].split())
    assert order == 549756390943 and blocks == 6
    slots = []
    row = 1
    for block in range(blocks):
        rotation, count = map(int, lines[row].split())
        assert rotation == 5 * block and count == 64
        row += 1
        table = {}
        for line in lines[row:row + count]:
            x, y, mask, sign, column = map(int, line.split())
            assert on_curve(field, (x, y))
            assert (mask, sign) not in table
            table[mask, sign] = {"point": (x, y), "column": column}
        row += count
        assert len(table) == 64
        slots.extend((table, table))
    assert row == len(lines)
    return (qx, qy), slots


def raw_choices(field, mask, rotation, table):
    w = sum(1 << (bit + 1) for bit in range(6) if mask >> bit & 1)
    assert w
    x = field.inv(w)
    rhs = x ^ field.inv(field.square(x))
    u = field.halftrace(rhs)
    choices = []
    for value in (u, u ^ 1):
        raw = (x, field.mul(x, value))
        assert on_curve(field, raw)
        rotated = raw
        for _ in range(rotation):
            rotated = (field.square(rotated[0]), field.square(rotated[1]))
        projected = times4(field, rotated)
        found = [sign for sign in (0, 1)
                 if table[mask, sign]["point"] == projected]
        assert len(found) == 1
        choices.append((rotated, found[0], table[mask, found[0]]["column"]))
    assert choices[0][1] != choices[1][1]
    return choices


def main():
    model = json.loads(MODEL.read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert model["target"] == protocol["target_q"]
    assert model["raw_lift_index"] in (0, 1)
    field = Field()
    target, slots = source(field)
    assert list(target) == model["target"]
    masks = model["masks"]
    assert len(masks) == 12 and all((mask, 0) in slots[i] for i, mask in enumerate(masks))
    seed = [masks[2*i] ^ masks[2*i + 1] for i in range(6)]
    assert seed[2] == seed[3] and seed[4] == seed[5]
    assert seed[2] ^ seed[4] < 8
    assert all(masks[2*i] < masks[2*i + 1] for i in range(6))
    columns = [slots[i][mask, 0]["column"] for i, mask in enumerate(masks)]
    assert len(set(columns)) == 12
    options = [raw_choices(field, mask, 5 * (i // 2), slots[i])
               for i, mask in enumerate(masks)]
    block_candidates = []
    for block in range(3):
        wanted_z = model["block_reciprocals"][block]
        assert wanted_z
        wanted_x = field.inv(wanted_z)
        candidates = []
        for four in itertools.product(*options[4*block:4*block + 4]):
            point = None
            for raw, _, _ in four:
                point = add(field, point, raw)
            if point is not None and point[0] == wanted_x:
                candidates.append((point, four))
        block_candidates.append(candidates)
    corrected = json.loads(LIFTS.read_text())["n41"]
    raw_target = tuple(corrected["preimages"][model["raw_lift_index"]]["point"])
    verified = []
    for first, second, third in itertools.product(*block_candidates):
        middle = add(field, first[0], second[0])
        if middle is None or middle[0] == 0:
            continue
        if field.inv(middle[0]) != model["intermediate_reciprocal"]:
            continue
        raw_sum = add(field, middle, third[0])
        if raw_sum != raw_target:
            continue
        leaves = [choice[0] for block in (first, second, third) for choice in block[1]]
        projected_sum = None
        for leaf in leaves:
            projected_sum = add(field, projected_sum, times4(field, leaf))
        assert projected_sum == target
        verified.append({"raw_sum": list(raw_sum),
                         "raw_points": [list(point) for point in leaves],
                         "signs": [choice[1] for block in (first, second, third)
                                   for choice in block[1]]})
    result = {"status": "PASS_VERIFIED_PUBLIC_RELATION" if verified else "NO_GROUP_LIFT",
              "target": model["target"], "raw_lift_index": model["raw_lift_index"],
              "masks": masks, "columns": columns, "seed_sums": seed,
              "block_candidate_counts": list(map(len, block_candidates)),
              "verified_relations": verified,
              "source_sha256": {"replay.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                "model_decoded.json": hashlib.sha256(MODEL.read_bytes()).hexdigest(),
                                "heldout_input.txt": hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                                "corrected_lifts.json": hashlib.sha256(LIFTS.read_bytes()).hexdigest()}}
    (HERE / "replay_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "block_candidate_counts": result["block_candidate_counts"],
                      "verified_relation_count": len(verified)}, sort_keys=True))


if __name__ == "__main__":
    main()
