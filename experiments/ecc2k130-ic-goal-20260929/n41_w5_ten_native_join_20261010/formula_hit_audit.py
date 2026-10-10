#!/usr/bin/env python3
"""Complete and check the native public relation in the archived SAT formula."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

here=Path(__file__).resolve().parent
gate_dir=here.parent/"n41_w5_ten_source_gate_20261010"
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location("n41_w5_ten_gate_run",gate_dir/"run.py")
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

sage=json.loads((here/"sage_hit_audit.json").read_text())
assert sage["status"]=="PASS_INDEPENDENT_SAGE_PUBLIC_GROUP_REPLAY"
hit=json.loads((here/"run/hits.jsonl").read_text().splitlines()[0])
public=json.loads((gate_dir/"public/result.json").read_text())
context=gate.setup()
qprime=tuple(public["transported_target_qprime"])
folder=here/"formula_replay"
folder.mkdir(exist_ok=False)
circuit,meta,targets,formula,stats,phases=gate.build_formula(folder,context,qprime)
archived=gate_dir/"public/system.xcnf"
assert sha(formula)==sha(archived)==public["formula"]["sha256"]
assert stats==public["formula"]
leaves,middle,total=gate.chain(context,hit["masks"],hit["signs"])
assert gate.regular(context,[*leaves,*middle,total])
assert list(total)==hit["raw_sum"] and total==targets[hit["target_preimage_index"]]
initial={}
for row,mask in zip(meta["masks"],hit["masks"]):
    initial.update({wire:mask>>i&1 for i,wire in enumerate(row)})
for i,wire in enumerate(meta["flags"]):
    initial[wire]=int(i==hit["target_preimage_index"])
for row,p in zip(meta["middle"],middle):
    u=gate.old.transformed(context["field"],p)
    initial.update({wire:u>>i&1 for i,wire in enumerate(row)})
assert len(initial)==meta["primary_variables"]
assignment=gate.old.witness_tools.complete_assignment(circuit,initial)
check=gate.old.base.check_xcnf(archived,assignment)
decoded=gate.decode(assignment,meta,context,qprime,targets)
assert decoded["valid"] and decoded["masks"]==hit["masks"]
assert decoded["signs"]==hit["signs"]
assert decoded["target_preimage_index"]==hit["target_preimage_index"]
assert decoded["raw_sum"]==hit["raw_sum"]
result={"status":"PASS_ARCHIVED_PUBLIC_XCNF_COMPLETE_ASSIGNMENT",
        "curve_id":public["curve_id"],"public_target_q":public["public_target_q"],
        "target_preimage_index":hit["target_preimage_index"],
        "masks":hit["masks"],"signs":hit["signs"],
        "formula":stats,"xcnf_check":check,"producer_relation":decoded,
        "source_sha256":{"archived_formula":sha(archived),
                         "native_hit":sha(here/"run/hits.jsonl"),
                         "sage_replay":sha(here/"sage_hit_audit.json"),
                         "gate_run":sha(gate_dir/"run.py"),
                         "gate_circuit":sha(gate_dir/"circuit.py"),
                         "script":sha(Path(__file__))}}
with (here/"formula_hit_audit.json").open("x") as f:
    json.dump(result,f,indent=2,sort_keys=True);f.write("\n")
print(json.dumps({"status":result["status"],"formula_sha256":stats["sha256"]}))
