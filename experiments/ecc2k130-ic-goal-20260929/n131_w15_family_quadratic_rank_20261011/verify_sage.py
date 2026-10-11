"""Independent Sage S3 replay and differently ordered quadratic rank check."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
TABLE = GOAL / "n131_w15_seedwise_fouratom_20261011/table.tsv"
AFFINE = GOAL / "n131_w15_family_affine_rank_20261011"
N = 131
DIM = 8516


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def independent_features(z):
    bits = [(z >> i) & 1 for i in range(129)] + [(z >> 130) & 1]
    assert (z & 1) == ((z >> 129) & 1)
    value = 1
    for i, bit in enumerate(bits):
        if bit:
            value |= 1 << (1 + i)
    position = 131
    # Quadratics are grouped by the larger index. The producer groups by
    # the smaller index, so the two rank checks use different column orders.
    for j in range(1, 130):
        if bits[j]:
            for i in range(j):
                if bits[i]:
                    value |= 1 << (position + i)
        position += j
    assert position == DIM and value.bit_length() <= DIM
    return value


def insert_low_pivot(basis, row):
    value = row
    while value:
        pivot_bit = value & -value
        pivot = pivot_bit.bit_length() - 1
        if pivot in basis:
            value ^= basis[pivot]
        else:
            basis[pivot] = value
            return True
    return False


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    prior = json.loads((AFFINE / "sage_replay.json").read_text())
    assert prior["status"] == "PASS_N131_W15_FIXED_SEED_AFFINE_RANK_SAGE_REPLAY"
    assert protocol["source_sha256"]["table.tsv"] == sha(TABLE)
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["positive_control_found"] and result["full_rank"]
    assert len(result["pivot_witnesses"]) == DIM
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**N, "z", modulus=t**N + t**13 + t**2 + t + 1)
    c = field.from_integer(protocol["fixed_first_reciprocal"])
    rotated_table = {}
    for row in TABLE.read_text().splitlines():
        coordinate, a, b = map(int, row.split())
        d = field.from_integer(coordinate)**(2**13)
        rotated_table[encode(d)] = (a, b)
    assert len(rotated_table) == 8288
    basis = {}
    for witness in result["pivot_witnesses"]:
        d = field.from_integer(witness["right_reciprocal"])
        z = field.from_integer(witness["output_z"])
        assert rotated_table[witness["right_reciprocal"]] == tuple(witness["right_masks"])
        cd = c * d
        assert (1 + cd**2) * z**2 + cd * z + (c + d)**2 == 0
        assert z.trace() == 0
        assert insert_low_pivot(basis, independent_features(witness["output_z"]))
    assert len(basis) == result["rank"] == DIM
    receipt = {"status": "PASS_N131_W15_QUADRATIC_RANK_SAGE_REPLAY",
               "curve_id": protocol["curve_id"],
               "feature_dimension": DIM, "independent_rank": len(basis),
               "s3_witnesses_checked": len(result["pivot_witnesses"]),
               "right_table_rows_checked": len(rotated_table),
               "prior_signed_group_replay_status": prior["status"],
               "source_sha256": {"protocol.json": sha(HERE / "protocol.json"),
                                 "result.json": sha(HERE / "result.json"),
                                 "table.tsv": sha(TABLE),
                                 "affine_sage_replay.json": sha(AFFINE / "sage_replay.json"),
                                 "sage_runtime_info.json": sha(HERE / "sage_runtime_info.json"),
                                 "verify_sage.py": sha(__file__)}}
    (HERE / "sage_replay.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "rank": receipt["independent_rank"]}))


if __name__ == "__main__":
    main()
