"""Check the guarded four-preimage formula on the full known assignment."""

import hashlib
import json
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
f = run.fixture()
p = run.protocol()
c, m, elapsed = run.old.build(f["raw_target_reciprocals"])


def bind(initial, wires, number):
    initial.update({wire: number >> bit & 1 for bit, wire in enumerate(wires)})


base = {}
for wires, number in zip(m["masks"], f["known_masks"]):
    bind(base, wires, number)
for wires, number in zip(m["pair_z"], f["pair_reciprocals"]):
    bind(base, wires, number)
for wires, number in zip(m["middle_z"], f["middle_reciprocals"]):
    bind(base, wires, number)
assert len(m["branch"]) == 0
assert len(m["target_flags"]) == 2
assert len(base) + 2 == len(m["primary_variables"])

records = []
for index in range(4):
    initial = dict(base)
    bind(initial, m["target_flags"], index)
    values = run.old.complete_assignment(c, initial)
    failed_clauses = sum(not any(values[abs(int(wire))] == int(int(wire) > 0)
                                 for wire in clause.split()[:-1])
                         for clause in c.clauses)
    failed_xors = sum(not (sum(values[abs(int(wire))] ^ int(int(wire) < 0)
                              for wire in row.split()[1:-1]) & 1)
                      for row in c.xors)
    assert failed_xors == 0
    if index == f["known_raw_preimage_index"]:
        assert failed_clauses == 0
    records.append({"raw_preimage_index": index,
                    "failed_clauses": failed_clauses,
                    "failed_native_xor_rows": failed_xors})

out = {"status": "PASS_GUARDED_FOUR_PREIMAGE_ASSIGNMENT",
       "target_original": f["public_target_original"],
       "known_raw_preimage_index": f["known_raw_preimage_index"],
       "formula": run.old.profile(c, m, elapsed),
       "records": records,
       "sha256": {"source": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "protocol": run.old.sha(HERE / "query/protocol.json"),
                  "circuit": run.old.sha(HERE / "circuit.py"),
                  "fixture": run.old.sha(run.W9 / "fixture.json")}}
(HERE / "full_assignment.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], [(v["raw_preimage_index"], v["failed_clauses"])
                      for v in records])
