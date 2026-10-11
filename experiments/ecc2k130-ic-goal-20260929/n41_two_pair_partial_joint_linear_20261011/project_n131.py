"""Challenge-width projection of the same sound partial-output relaxation."""

import hashlib
import importlib.util
import json
import random
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TABLE = ROOT / "n131_w18_seedwise_fouratom_20261011/table.tsv"
PRIOR = ROOT / "n131_w18_seedwise_hashjoin_20261011/run_receipt.json"
WIDTHS = (0, 2, 4, 6, 8, 10)
SEED = 13686
SAMPLE_SEED = 202610111955
CONTROL_COUNT = 24

spec = importlib.util.spec_from_file_location("joint_n41", HERE / "run.py")
joint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(joint)
joint.N = 131
joint.MASK = (1 << 131)-1
joint.MOD_LOW = (1 << 13) | (1 << 2) | (1 << 1) | 1


def image_basis(seed_mask, rotation):
    s = joint.frob(seed_mask << 1, rotation)
    generators, pivots = [], {}
    for bit in range(18):
        a = joint.frob(1 << (bit+1), rotation)
        value = joint.sq(a) ^ joint.mul(s, a)
        reduced = value
        while reduced:
            pivot = reduced.bit_length()-1
            if pivot in pivots:
                reduced ^= pivots[pivot]
            else:
                pivots[pivot] = reduced
                generators.append(value)
                break
    assert len(generators) == 17
    return generators


joint.image_basis = image_basis


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(words):
    return sum(int(word) << (64*i) for i, word in enumerate(words))


def table_rows():
    return [(int(a), int(b), int(c)) for a,b,c in
            (line.split() for line in TABLE.read_text().splitlines())]


def freeze():
    prior = json.loads(PRIOR.read_text())
    case = prior["cases"][0]["native_result"]
    hit = case["hits"][0]
    positive = [decode(hit["first_reciprocal"]),
                decode(hit["second_reciprocal"])]
    target_z = decode(case["output_z"])
    rows = table_rows()
    assert len(rows) == 65868
    by_masks = {}
    for c,a,b in rows:
        by_masks.setdefault((a,b), set()).add(c)
    assert positive[0] in by_masks[tuple(hit["first_masks"])]
    assert positive[1] in {
        joint.frob(c, 13) for c in by_masks[tuple(hit["second_masks"])]}
    rng = random.Random(SAMPLE_SEED)
    control_ids = [[rng.randrange(len(rows)), rng.randrange(len(rows))]
                   for _ in range(CONTROL_COUNT)]
    panel = {"status": "FROZEN_N131_W18_JOINT_LINEAR_PROJECTION",
             "candidate_id": None, "seed_mask": SEED,
             "rotations": [26, 39], "target_z": target_z,
             "positive_coordinates": positive,
             "control_table_ids": control_ids,
             "input_law": "uniform independent exact fixed-seed pair outputs with replacement",
             "sample_seed": SAMPLE_SEED, "widths": list(WIDTHS)}
    (HERE / "n131_panel.json").write_text(json.dumps(panel, indent=2, sort_keys=True)+"\n")
    protocol = {"status": "FROZEN_N131_JOINT_LINEAR_PROJECTION_PROTOCOL",
                "candidate_id": None,
                "limits": {"workers": 1, "seconds": 120, "rss_bytes": 4294967296},
                "sha256": {"project": sha(__file__), "joint": sha(HERE / "run.py"),
                           "panel": sha(HERE / "n131_panel.json"),
                           "table": sha(TABLE), "prior": sha(PRIOR)}}
    (HERE / "n131_protocol.json").write_text(json.dumps(protocol, indent=2, sort_keys=True)+"\n")
    print(panel["status"], "controls", len(control_ids))


def evaluate():
    protocol = json.loads((HERE / "n131_protocol.json").read_text())
    panel = json.loads((HERE / "n131_panel.json").read_text())
    assert protocol["sha256"] == {
        "project": sha(__file__), "joint": sha(HERE / "run.py"),
        "panel": sha(HERE / "n131_panel.json"),
        "table": sha(TABLE), "prior": sha(PRIOR)}
    rows = table_rows()
    target = panel["target_z"]
    assert joint.trace(target) == 0
    cases = [("positive", panel["positive_coordinates"])]
    cases.extend((f"control_{i}",
                  [rows[a][0], joint.frob(rows[b][0], 13)])
                 for i, (a,b) in enumerate(panel["control_table_ids"]))
    s1, s2 = (joint.frob(SEED << 1, rotation) for rotation in (26, 39))
    result_rows = []
    start = time.monotonic_ns()
    for label, (c,d) in cases:
        left = {"c": c, "s": s1, "seed_mask": SEED, "rotation": 26}
        right = {"c": d, "s": s2, "seed_mask": SEED, "rotation": 39}
        decisions = {str(width): joint.joint_consistency(left, right, target, width)
                     for width in WIDTHS}
        if label == "positive":
            assert all(v["joint"] and v["left_local"] and v["right_local"]
                       for v in decisions.values())
        else:
            assert all(v["left_local"] and v["right_local"]
                       for v in decisions.values())
        result_rows.append({"label": label, "coordinates": [c,d],
                            "decisions": decisions})
        if time.monotonic_ns()-start > 120_000_000_000:
            raise TimeoutError("frozen 120-second cap")
    summary = {str(width): {
        "positive_passing": result_rows[0]["decisions"][str(width)]["joint"],
        "controls_passing_both_local": sum(
            row["decisions"][str(width)]["left_local"] and
            row["decisions"][str(width)]["right_local"]
            for row in result_rows[1:]),
        "controls_passing_joint": sum(
            row["decisions"][str(width)]["joint"] for row in result_rows[1:]),
        "rank_min": min(row["decisions"][str(width)]["rank"]
                        for row in result_rows),
        "rank_max": max(row["decisions"][str(width)]["rank"]
                        for row in result_rows),
        "variables": result_rows[0]["decisions"][str(width)]["variables"]}
               for width in WIDTHS}
    out = {"status": "COMPLETE_N131_JOINT_LINEAR_PROJECTION",
           "candidate_id": None, "controls": CONTROL_COUNT,
           "elapsed_ns": time.monotonic_ns()-start,
           "summary": summary, "rows": result_rows,
           "protocol_sha256": sha(HERE / "n131_protocol.json")}
    (HERE / "n131_result.json").write_text(json.dumps(out, indent=2, sort_keys=True)+"\n")
    print(out["status"], out["elapsed_ns"]/1e9)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "evaluate"):
        raise SystemExit("usage: project_n131.py freeze|evaluate")
    (freeze if sys.argv[1] == "freeze" else evaluate)()
