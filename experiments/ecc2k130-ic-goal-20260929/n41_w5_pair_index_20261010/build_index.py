#!/usr/bin/env sage -python
"""Enumerate exact unordered W5 same-rotation pair-output signatures."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "n41_w5_ten_source_gate_20261010"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("n41_w5_source_for_pair_index", SOURCE / "run.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signatures():
    context = old.setup()
    field, curve = context["field"], context["curve"]
    raw, columns = context["raw"], context["columns"]
    entries = {}
    accepted_rows = 0
    rejected_exceptional = 0
    for mask_a in sorted(raw):
        for mask_b in sorted(raw):
            if mask_a >= mask_b or columns[mask_a] == columns[mask_b]:
                continue
            for sign_a in (0, 1):
                for sign_b in (0, 1):
                    point = curve.add(raw[mask_a][sign_a],
                                      raw[mask_b][sign_b])
                    if point is None or point[0] in (0, 1):
                        rejected_exceptional += 1
                        continue
                    accepted_rows += 1
                    z = old.old.transformed(field, point)
                    key = (mask_a, mask_b, z)
                    entry = entries.setdefault(key, {
                        "mask_a": mask_a, "mask_b": mask_b,
                        "z_local": z, "sign_options": [],
                        "raw_output_points": []})
                    entry["sign_options"].append([sign_a, sign_b])
                    entry["raw_output_points"].append(list(point))
    result = [entries[key] for key in sorted(entries)]
    assert accepted_rows == 528 and rejected_exceptional == 0
    assert all(len(row["sign_options"]) == 2 for row in result)
    assert len(result) == 264
    assert len({row["z_local"] for row in result}) <= len(result)
    return result, accepted_rows, rejected_exceptional


def main():
    entries, accepted, exceptional = signatures()
    geometry = SOURCE / "geometry_result.json"
    record = {"status": "PASS_EXACT_W5_UNORDERED_PAIR_INDEX",
              "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
              "source_width": 5,
              "accepted_unordered_signed_pair_rows": accepted,
              "exceptional_pair_rows": exceptional,
              "signature_count": len(entries),
              "distinct_transformed_outputs": len({row["z_local"] for row in entries}),
              "selection_rule": "mask_a < mask_b, distinct folded columns, regular group sum, then deduplicate (mask_a,mask_b,z)",
              "entries": entries,
              "source_sha256": {"script": sha(Path(__file__)),
                                "geometry": sha(geometry),
                                "source_runner": sha(SOURCE / "run.py"),
                                "source_audit": sha(SOURCE / "sage_geometry_audit.json")}}
    with (HERE / "pair_index.json").open("x") as out:
        json.dump(record, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": record["status"],
                      "signatures": len(entries),
                      "outputs": record["distinct_transformed_outputs"]}))


if __name__ == "__main__":
    main()
