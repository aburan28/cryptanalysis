#!/usr/bin/env python3
"""Freeze unpinned-seed N41 XCNFs and a complete constructed assignment."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

here=Path(__file__).resolve().parent
root=here.parent
field_path=root.parent/"koblitz-polynomial-w-pair-20260925/pair_oracle.py"
circuit_base_path=root.parent/"koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py"
method_path=here/"circuit.py"
mixed=root/"n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
w6=root/"n41_upper_xor_projection_20261010/w6_input.txt"
solver=Path("/opt/homebrew/bin/cryptominisat5")


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.path.insert(0,str(field_path.parent))
from pair_oracle import Field
from karatsuba_circuit import KaratsubaCircuit
method=load("mixed_fouratom_n41_circuit",method_path)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def complete_assignment(circuit,initial):
    definitions={int(out):("and",int(a),int(b))
                 for (a,b),out in circuit.and_cache.items()}
    for line in circuit.xors:
        literals=[int(x) for x in line.split()[1:-1]]
        definitions[abs(literals[0])]=("xor",literals)
    values=[None]*circuit.next_var
    for wire,bit in initial.items():values[wire]=bit
    for wire in range(1,circuit.next_var):
        if values[wire] is not None:continue
        definition=definitions.get(wire)
        if definition is None:raise RuntimeError(f"unassigned primary wire {wire}")
        if definition[0]=="and":
            def val(x):return 1 if x==-1 else 0 if x==0 else values[x]
            values[wire]=val(definition[1])&val(definition[2])
        else:
            literals=definition[1]
            value=int(literals[0]>0)
            for x in literals[1:]:value^=values[abs(x)]^int(x<0)
            values[wire]=value
    return {wire:bool(values[wire]) for wire in range(1,circuit.next_var)}


def check_xcnf(path,assignment):
    clauses=xors=0
    for line in path.open():
        if not line.strip() or line.startswith(("c","p ")):continue
        literals=[int(x) for x in line.split()[1 if line.startswith("x ") else 0:-1]]
        if line.startswith("x "):
            assert sum(assignment[abs(x)]^(x<0) for x in literals)%2==1
            xors+=1
        else:
            assert any(assignment[abs(x)]==(x>0) for x in literals)
            clauses+=1
    return {"cnf_clauses":clauses,"xor_rows":xors}


lines=w6.read_text().splitlines()
columns={}
for line in lines[2:66]:
    x,y,mask,sign,column=map(int,line.split())
    assert sign in (0,1)
    if mask in columns:assert columns[mask]==column
    columns[mask]=column
assert len(columns)==32 and len(set(columns.values()))==26
panel=json.loads(mixed.read_text())["panels"]["41"]
assert panel["rotations"]==[10,15] and panel["source_masks"]==[2,3,6,7]
field=Field(41,[0,3])
rows={}
for case in ("positive","trace_zero_control"):
    z=panel["positive_z" if case=="positive" else "trace_zero_control_z"]
    circuit=KaratsubaCircuit(41,[0,3])
    meta=method.build(circuit,field,6,panel["rotations"],columns,z)
    path=here/f"n41_{case}.xcnf"
    circuit.write(path)
    check=None
    if case=="positive":
        initial={}
        for row,mask in zip(meta["masks"],panel["source_masks"]):
            initial.update({wire:(mask>>i)&1 for i,wire in enumerate(row)})
        for row,value in zip(meta["outputs"],panel["pair_outputs_reciprocal"]):
            initial.update({wire:(value>>i)&1 for i,wire in enumerate(row)})
        assert len(initial)==meta["primary_variables"]
        assignment=complete_assignment(circuit,initial)
        check=check_xcnf(path,assignment)
    rows[case]={"target_z":z,"formula_sha256":sha(path),
                "variables":circuit.next_var-1,"clauses":len(circuit.clauses),
                "xor_rows":len(circuit.xors),"and_gates":circuit.and_count,
                "seed_equality_rows":meta["seed_equality_rows"],
                "duplicate_column_clauses":meta["duplicate_column_clauses"],
                "complete_constructed_assignment":check}
sources={"circuit.py":method_path,"freeze.py":here/"freeze.py",
         "run.py":here/"run.py","field_source":field_path,
         "circuit_base":circuit_base_path,
         "mixed_inputs":mixed,"w6_input":w6,"solver":solver}
protocol={"status":"FROZEN_BEFORE_UNPINNED_SEED_N41_SAT",
          "curve_id":panel["curve_id"],"field":"GF(2^41), t^41+t^3+1",
          "rotations":panel["rotations"],"factor_base_points_B":384,
          "folded_columns_K":26,"worker_count":1,
          "parent_cap_seconds_per_case":20,"rss_cap_bytes":4294967296,
          "solver_flags":["--threads=1","--xor=0","--printsol=1",
                          "--random=20261010","--maxtime=18"],
          "case_order":["positive","trace_zero_control"],
          "cases":rows,
          "source_sha256":{name:sha(path) for name,path in sources.items()}}
(here/"protocol.json").write_text(json.dumps(protocol,indent=2,sort_keys=True)+"\n")
print(json.dumps({"status":protocol["status"],"cases":rows},sort_keys=True))
