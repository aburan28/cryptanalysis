#!/usr/bin/env python3
"""Complete all public-join witnesses as assignments to the frozen XCNF."""
import hashlib
import json
from pathlib import Path
import run_v2

here = Path(__file__).resolve().parent
source = run_v2.source
base = source.base
method = source.method
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
protocol = json.loads((here / "protocol_v2.json").read_text())
assert protocol["source_sha256"]["run"] == sha(here / "run.py")
assert protocol["source_sha256"]["circuit"] == sha(here / "circuit.py")
public = json.loads((here / "public/result.json").read_text())
assert public["status"] == "CENSORED_TIME"
assert public["formula"]["sha256"] == sha(here / "public/system.xcnf")
context = source.setup()
field, curve, q = context["field"], context["curve"], context["public_q"]
raw_targets = base.target_preimages(field, curve, q)
target_us = [source.transformed(field, point) for point in raw_targets]
circuit = base.KaratsubaCircuit(41, [0, 3])
meta = method.build(circuit, context["bases_w"],
                    [context["columns"]] * method.BLOCKS, target_us)
assert circuit.next_var - 1 == public["formula"]["variables"]
assert len(circuit.clauses) == public["formula"]["clauses"]
assert len(circuit.xors) == public["formula"]["xor_rows"]
checks = []
for line in (here / "join_hits.jsonl").open():
    hit = json.loads(line)
    states = [context["states"][i][mask][sign]
              for i, (mask, sign) in enumerate(zip(hit["masks"], hit["signs"]))]
    middle, total = source.chain(curve, [row["point"] for row in states])
    assert curve.mul(4, total) == q
    endpoint = raw_targets.index(total)
    initial = {}
    for mask_wires, mask in zip(meta["masks"], hit["masks"]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(mask_wires)})
    for index, wire in enumerate(meta["flags"]):
        initial[wire] = int(index == endpoint)
    for wires, values in ((meta["leaves"], [row["z"] for row in states]),
                          (meta["middle"], [source.transformed(field, p) for p in middle])):
        for row, value in zip(wires, values):
            if value is None:
                raise ValueError("undefined transformed coordinate")
            initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    model = source.witness_tools.complete_assignment(circuit, initial)
    check = base.check_xcnf(here / "public/system.xcnf", model)
    relation = source.decode(model, meta, context, q, raw_targets)
    if not relation["valid"] or relation["masks"] != hit["masks"] or relation["signs"] != hit["signs"]:
        raise ValueError("frozen formula model failed relation replay")
    checks.append({"masks": hit["masks"], "signs": hit["signs"],
                   "target_preimage_index": endpoint, "xcnf_check": check})
result = {"status": "PASS_THREE_FROZEN_PUBLIC_XCNF_ASSIGNMENTS",
          "verified_assignment_count": len(checks), "checks": checks,
          "source_sha256": {"public_formula": sha(here / "public/system.xcnf"),
                            "public_result": sha(here / "public/result.json"),
                            "join_hits": sha(here / "join_hits.jsonl"),
                            "script": sha(Path(__file__))}}
assert len(checks) == 3
path = here / "full_formula_join_audit.json"
with path.open("x") as out:
    json.dump(result, out, indent=2, sort_keys=True)
    out.write("\n")
print(json.dumps({"status": result["status"], "assignments": len(checks)}))
