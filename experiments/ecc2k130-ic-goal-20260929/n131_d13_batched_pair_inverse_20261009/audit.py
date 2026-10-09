#!/usr/bin/env sage -python
"""Independently replay batched-inverse output pairs as curve additions."""

import hashlib
import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_d13_same_rotation_pairs_20261009"
CODEGEN = HERE.parents[2] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def phi(onb, basis, code):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    return onb.fromCoords(mask)


def point(onb, curve, basis, code):
    value = phi(onb, basis, code)
    return curve.pointFromX(onb.add(onb.inv(value), onb.one()))


def output_mask(onb, total):
    if total is None or total[0] == onb.one():
        return None
    return onb.toCoords(onb.inv(onb.add(total[0], onb.one())))


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, result_path = HERE / "protocol.json", HERE / "result.json"
    protocol, result = json.loads(protocol_path.read_text()), json.loads(result_path.read_text())
    paths = {"run": HERE / "run.py", "audit": HERE / "audit.py",
             "field": CODEGEN / "field.py",
             "pivots": SOURCE / "pivots.bin",
             "valid_codes": SOURCE / "valid_codes.json",
             "source_result": SOURCE / "result.json",
             "runtime": HERE / "runtime_info.json"}
    if (protocol["status"] != "FROZEN" or result["status"] != "PASS_EXACT_MATCH" or
            result["source_sha256"]["protocol"] != sha(protocol_path) or
            any(protocol["source_sha256"][name] != sha(path)
                for name, path in paths.items()) or
            result["source_sha256"]["run"] != sha(paths["run"])):
        raise ValueError("frozen source or receipt digest changed")
    source = json.loads(paths["source_result"].read_text())
    if source["status"] != "PASS_EXACT_PAIR_INVERSE_CONTROLS":
        raise ValueError("source pair inverse receipt changed")
    rng = random.Random(20261009225000)
    inputs = protocol["inputs"]
    if len(inputs) != 64 or len(result["input_pair_results"]) != 64:
        raise ValueError("input count changed")
    for i in range(32):
        item = source["positive_controls"][i]
        if (inputs[i]["kind"] != "positive" or
                inputs[i]["z_mask"] != item["output_phi_mask"] or
                inputs[i]["pair"] != item["codes"]):
            raise ValueError("source positive input changed")
    seen = {item["z_mask"] for item in inputs[:32]}
    for i in range(32, 64):
        expected = rng.randrange(2, 1 << 131)
        while expected in seen:
            expected = rng.randrange(2, 1 << 131)
        seen.add(expected)
        if (inputs[i]["kind"] != "uniform_field_control" or
                inputs[i]["z_mask"] != expected):
            raise ValueError("control input law changed")
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    basis = [int(mask, 16) for mask in protocol["basis_masks_hex"]]
    valid = set(json.loads(paths["valid_codes"].read_text()))
    pair_replays = 0
    for i, saved in enumerate(result["input_pair_results"]):
        if (saved["input_index"] != i or saved["z_mask"] != inputs[i]["z_mask"] or
                saved["kind"] != inputs[i]["kind"]):
            raise ValueError("pair result/input mismatch")
        pairs = [tuple(pair) for pair in saved["pairs"]]
        if pairs != sorted(set(pairs)):
            raise ValueError("pair output not unique and sorted")
        if inputs[i]["kind"] == "positive" and tuple(inputs[i]["pair"]) not in pairs:
            raise ValueError("positive input pair absent")
        for a, b in pairs:
            if a >= b or a not in valid or b not in valid:
                raise ValueError("accepted selector pair invalid")
            left, right = point(onb, curve, basis, a), point(onb, curve, basis, b)
            if left is None or right is None:
                raise ValueError("accepted selector lacks point lift")
            outputs = {output_mask(onb, curve.add(left, right)),
                       output_mask(onb, curve.add(left, curve.neg(right)))}
            if saved["z_mask"] not in outputs:
                raise ValueError("accepted pair does not produce output")
            pair_replays += 1
    raw = result["raw"]
    if len(raw) != 2 * 64 * 3:
        raise ValueError("raw comparison has missing cells")
    cells = {}
    for row in raw:
        key = (row["repetition"], row["input_index"], row["method"])
        if key in cells or row["wall_ns"] <= 0 or row["pair_count"] < 0:
            raise ValueError("invalid raw comparison row")
        cells[key] = row
    for rep in range(2):
        for i in range(64):
            counts = [cells[(rep, i, method)]["pair_count"]
                      for method in protocol["methods"]]
            if counts != [len(result["input_pair_results"][i]["pairs"])] * 3:
                raise ValueError("method pair count mismatch")
    for method in protocol["methods"]:
        values = [row["wall_ns"] for row in raw if row["method"] == method]
        if int(statistics.median(values)) != result["method_wall_ns"][method]["median_ns"]:
            raise ValueError("receipt median differs from raw rows")
    receipt = {"kind": "n131_d13_batched_pair_inverse_independent_audit",
               "status": "PASS_GROUP_REPLAY_AND_RAW_RECEIPT",
               "candidate_id": None, "run_id": None,
               "pair_replays": pair_replays, "input_count": len(inputs),
               "timing_rows_checked": len(raw),
               "source_sha256": {"protocol": sha(protocol_path),
                                 "result": sha(result_path),
                                 "audit": sha(Path(__file__)),
                                 "source_audit": sha(SOURCE / "audit.json")}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "pair_replays": pair_replays,
                      "timing_rows_checked": len(raw)}))


if __name__ == "__main__":
    main()
