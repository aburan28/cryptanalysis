#!/usr/bin/env sage -python
"""Replay an ordinary full XCNF model as an exact Sage curve relation."""

import hashlib
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
R = 680564733841876926932320129493409985129
ROTATIONS = [0, 16, 32, 48, 64, 80, 96, 112]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "ordinary_model_replay_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "model_audit": HERE / "ordinary_audit_result.json",
             "target": BASE / "target_preimages.json", "runtime": HERE / "sage_runtime_info.json",
             "support": BASE / "support_result.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    model = json.loads(paths["model_audit"].read_text())
    target = json.loads(paths["target"].read_text())
    assert model["status"] == "PASS_RELAXED_SOURCE_ORDINARY_XCNF_MODEL_AUDIT"
    assert model["all_pairs_source_valid"]

    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(poly([(int(value) >> bit) & 1 for bit in range(131)]))

    def encode(value):
        return sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))

    def point(coords):
        return curve(decode(coords[0]), decode(coords[1]))

    def coordinate(mask):
        return sum((field(t**(bit+1)) for bit in range(18) if mask >> bit & 1),
                   field.zero())

    def half_trace(value):
        acc, term = field.zero(), value
        for _ in range(66):
            acc += term
            term = term**4
        assert acc**2 + acc == value
        return acc

    def reciprocal(raw):
        if raw == curve(0) or raw[0] == 1:
            return None
        return 1/(raw[0]+1)

    options = []
    for slot, masks in enumerate(model["source_mask_pairs"]):
        source_points = []
        for mask in masks:
            u = half_trace(coordinate(mask))
            assert u != 0
            x = 1 + 1/u
            source_points.append(curve.lift_x(x, all=True))
        assert len(source_points[0]) == len(source_points[1]) == 2
        z = decode(model["unrotated_pair_output_z"][slot])
        slot_options = {}
        for left, right in itertools.product(*source_points):
            raw = left + right
            if reciprocal(raw) != z:
                continue
            rotation = ROTATIONS[slot]
            rotated = curve(raw[0]**(1 << rotation), raw[1]**(1 << rotation))
            slot_options[(encode(rotated[0]), encode(rotated[1]))] = rotated
        assert len(slot_options) == 2
        options.append(list(slot_options.values()))

    target_z = decode(model["target_z"])
    target_points = [point(item["point"]) for item in target["preimages"]]
    assert target_points[0] != curve(0)
    assert reciprocal(target_points[0]) == target_z
    public_q = point(target["public_target"])
    assert all(4*preimage == public_q for preimage in target_points)
    assert R*public_q == curve(0)
    matches = []
    for choices in itertools.product(range(2), repeat=8):
        running = options[0][choices[0]]
        intermediates_match = True
        for slot in range(1, 8):
            running += options[slot][choices[slot]]
            if slot < 7 and reciprocal(running) != decode(model["intermediate_z"][slot-1]):
                intermediates_match = False
                break
        if not intermediates_match or reciprocal(running) != target_z:
            continue
        matches.append({"choices": list(choices),
                        "raw_point": [encode(running[0]), encode(running[1])],
                        "target_preimage_index": next((i for i, preimage in
                            enumerate(target_points) if preimage == running), None),
                        "projects_to_public_target": 4*running == public_q})
    columns = [column for slot in model["source_folded_columns"] for column in slot]
    result = {"status": "PASS_EXACT_CURVE_RELATION_REPLAY" if matches else
                         "NO_CURVE_RELATION_FROM_SAT_MODEL",
              "model_matches": matches,
              "unique_folded_columns": len(set(columns)),
              "total_source_atoms": len(columns),
              "all_source_columns_distinct": len(set(columns)) == len(columns),
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "ordinary_model_replay.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "matches": len(matches),
                      "unique_folded_columns": result["unique_folded_columns"],
                      "projects_to_public_target": any(item["projects_to_public_target"]
                                                       for item in matches)}))


if __name__ == "__main__":
    main()
