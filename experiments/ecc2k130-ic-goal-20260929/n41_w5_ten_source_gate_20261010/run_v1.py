#!/usr/bin/env python3
"""Frozen N41 W5 ten-source control and unpinned public-point SAT query."""
import argparse
import hashlib
import importlib.util
import itertools
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

import psutil

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/"n41_n131_seven_diagonal_20261009"
sys.path.insert(0,str(OLD))
import run as old
spec=importlib.util.spec_from_file_location("n41_w5_ten_circuit",HERE/"circuit.py")
method=importlib.util.module_from_spec(spec)
spec.loader.exec_module(method)

GEOMETRY=HERE/"geometry_result.json"
AUDIT=HERE/"sage_geometry_audit.json"
RUNTIME=HERE/"sage_runtime_info.json"
CONTROL=HERE/"control.json"
PROTOCOL=HERE/"protocol.json"
SOLVER=Path("/opt/homebrew/bin/cryptominisat5")
R=549756390943

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            digest.update(block)
    return digest.hexdigest()

def save(path,value):
    with Path(path).open("x") as f:
        json.dump(value,f,indent=2,sort_keys=True)
        f.write("\n")

def sources():
    return {"run":Path(__file__),"circuit":Path(method.__file__),
            "geometry":GEOMETRY,"geometry_audit":AUDIT,"runtime":RUNTIME,
            "old_run":OLD/"run.py","base":Path(old.base.__file__),
            "witness":Path(old.witness_tools.__file__),"solver":SOLVER}

def setup():
    g=json.loads(GEOMETRY.read_text())
    a=json.loads(AUDIT.read_text())
    assert g["status"]=="PASS_FULL_MASK_AND_PROJECTED_GROUP_ENUMERATION"
    assert a["status"]=="PASS_EXACT_SAGE_GEOMETRY_AND_GROUP_BASE"
    field=old.base.Field(41,[0,3])
    curve=old.base.Curve(field,0)
    q=tuple(g["public_target_q"])
    assert curve.on_curve(q) and curve.mul(R,q) is None
    lam=json.loads((HERE.parent/"n41_seven_linear_source_20261009/protocol.json").read_text())["lambda_mod_r"]
    assert (lam*lam+lam+2)%R==0 and curve.mul(lam,q)==old.point_frob(field,q,1)
    return {"geometry":g,"field":field,"curve":curve,"q":q,"lambda":lam,
            "columns":{int(k):tuple(v) for k,v in g["mask_columns"].items()},
            "raw":{int(k):[tuple(p) for p in v]
                   for k,v in g["raw_points"].items()}}

def qprime_of(context,q):
    result=context["curve"].mul(pow(1+context["lambda"],-1,R),q)
    assert result is not None
    assert context["curve"].add(result,old.point_frob(context["field"],result,1))==q
    return result

def chain(context,masks,signs):
    f,c=context["field"],context["curve"]
    leaves=[old.point_frob(f,context["raw"][mask][sign],rotation)
            for mask,sign,rotation in zip(masks,signs,context["geometry"]["rotations"])]
    mid=[c.add(leaves[2*i],leaves[2*i+1]) for i in range(5)]
    mid.extend((c.add(mid[0],mid[1]),c.add(mid[2],mid[3])))
    mid.append(c.add(mid[5],mid[6]))
    total=c.add(mid[7],mid[4])
    return leaves,mid,total

def regular(context,points):
    return all(p is not None and p[0] not in (0,1) for p in points)

def make_control(context):
    rng=random.Random(202610101855)
    groups={}
    for mask,column in context["columns"].items():
        groups.setdefault(column,[]).append(mask)
    if len(groups)<10:
        raise ValueError("fewer than ten folded columns")
    keys=sorted(groups)
    for attempt in range(1000):
        chosen=rng.sample(keys,10)
        masks=[rng.choice(groups[key]) for key in chosen]
        signs=[rng.randrange(2) for _ in range(10)]
        leaves,mid,total=chain(context,masks,signs)
        if not regular(context,[*leaves,*mid,total]):
            continue
        qprime=context["curve"].mul(4,total)
        if qprime is None:
            continue
        q=context["curve"].add(qprime,old.point_frob(context["field"],qprime,1))
        if q is None:
            continue
        try:
            targets=old.base.target_preimages(context["field"],context["curve"],qprime)
        except AssertionError:
            continue
        if total not in targets:
            raise ValueError("constructed target fiber lost raw sum")
        return {"kind":"n41_w5_ten_source_control","attempt":attempt,
                "seed":202610101855,"masks":masks,"signs":signs,
                "folded_columns":[list(k) for k in chosen],
                "raw_leaves":[list(p) for p in leaves],
                "leaf_u":[old.transformed(context["field"],p) for p in leaves],
                "middle_u":[old.transformed(context["field"],p) for p in mid],
                "raw_sum":list(total),"qprime":list(qprime),"q":list(q),
                "target_preimage_index":targets.index(total)}
    raise RuntimeError("could not construct regular ten-source control")

def freeze():
    assert not PROTOCOL.exists() and not CONTROL.exists()
    assert json.loads(RUNTIME.read_text())["status"]=="verified"
    context=setup()
    control=make_control(context)
    save(CONTROL,control)
    g=context["geometry"]
    protocol={"kind":"n41_w5_ten_source_public_query",
              "status":"FROZEN_BEFORE_FORMULA","proposal_id":"Q20261010185500",
              "candidate_id":None,"run_id":None,"curve_id":g["curve_id"],
              "public_target_q":list(context["q"]),"target_count":1,
              "summands":10,"source_dimension":5,
              "rotations":g["rotations"],
              "rational_masks_per_block":g["rational_source_masks"],
              "actual_factor_base_points_B":g["actual_subgroup_factor_base_points_B"],
              "effective_folded_columns_K":g["folded_columns_K"],
              "online_cap_seconds":120,"solver_parent_wall_cap_seconds":115,
              "rss_cap_bytes":4*1024**3,"workers":1,
              "solver_flags":["--threads=1","--xor=0","--printsol=1",
                              "--random=20261010","--maxconfl=2000000"],
              "input_law":"one frozen public subgroup point; ten rational source masks, signs, and intermediate coordinates unpinned",
              "model_rule":"full XCNF check, ten distinct folded columns, exact raw group sum and cofactor-four transport, independent checked Sage replay",
              "source_sha256":{name:sha(path) for name,path in sources().items()},
              "control_sha256":sha(CONTROL)}
    save(PROTOCOL,protocol)
    print(json.dumps({"status":protocol["status"],"control_attempt":control["attempt"],
                      "B":protocol["actual_factor_base_points_B"],
                      "K":protocol["effective_folded_columns_K"]}))

def verify_freeze():
    p=json.loads(PROTOCOL.read_text())
    if (p["status"]!="FROZEN_BEFORE_FORMULA" or
            p["source_sha256"]!={name:sha(path) for name,path in sources().items()} or
            p["control_sha256"]!=sha(CONTROL)):
        raise ValueError("frozen source or control drift")
    return p

def build_formula(folder,context,qprime):
    began=time.monotonic()
    targets=old.base.target_preimages(context["field"],context["curve"],qprime)
    target_us=[old.transformed(context["field"],p) for p in targets]
    fiber_seconds=time.monotonic()-began
    circuit=old.base.KaratsubaCircuit(41,[0,3])
    meta=method.build(circuit,context["geometry"]["bases_u"],
                      context["columns"],target_us)
    formula=folder/"system.xcnf"
    circuit.write(formula)
    stats={"variables":circuit.next_var-1,"clauses":len(circuit.clauses),
           "xor_rows":len(circuit.xors),"and_gates":circuit.and_count,
           "duplicate_column_clauses":meta["duplicate_column_clauses"],
           "bytes":formula.stat().st_size,"sha256":sha(formula)}
    return circuit,meta,targets,formula,stats,{
        "target_fiber_seconds":fiber_seconds,
        "target_formula_seconds":time.monotonic()-began-fiber_seconds}

def bits(model,row):
    return sum(int(model[wire])<<i for i,wire in enumerate(row))

def decode(model,meta,context,qprime,targets):
    masks=[bits(model,row) for row in meta["masks"]]
    flags=[i for i,wire in enumerate(meta["flags"]) if model[wire]]
    if len(flags)!=1 or any(mask not in context["columns"] for mask in masks):
        return {"valid":False,"reason":"mask_or_flag","masks":masks}
    keys=[context["columns"][mask] for mask in masks]
    if len(set(keys))!=10:
        return {"valid":False,"reason":"duplicate_column","masks":masks}
    leaf_u=[bits(model,row) for row in meta["leaves"]]
    middle_u=[bits(model,row) for row in meta["middle"]]
    for signs in itertools.product((0,1),repeat=10):
        leaves,mid,total=chain(context,masks,signs)
        if not regular(context,[*leaves,*mid,total]):
            continue
        if ([old.transformed(context["field"],p) for p in leaves]!=leaf_u or
                [old.transformed(context["field"],p) for p in mid]!=middle_u or
                total!=targets[flags[0]] or context["curve"].mul(4,total)!=qprime):
            continue
        return {"valid":True,"masks":masks,"signs":list(signs),
                "folded_columns":[list(k) for k in keys],
                "target_preimage_index":flags[0],
                "raw_leaves":[list(p) for p in leaves],"raw_sum":list(total),
                "target_qprime":list(qprime)}
    return {"valid":False,"reason":"group_chain","masks":masks,
            "target_preimage_index":flags[0]}

def preflight():
    verify_freeze()
    folder=HERE/"preflight"
    folder.mkdir(exist_ok=False)
    context=setup()
    control=json.loads(CONTROL.read_text())
    qprime=tuple(control["qprime"])
    circuit,meta,targets,formula,stats,phases=build_formula(folder,context,qprime)
    initial={}
    for row,mask in zip(meta["masks"],control["masks"]):
        initial.update({wire:mask>>i&1 for i,wire in enumerate(row)})
    for i,wire in enumerate(meta["flags"]):
        initial[wire]=int(i==control["target_preimage_index"])
    for row,value in zip(meta["middle"],control["middle_u"]):
        initial.update({wire:value>>i&1 for i,wire in enumerate(row)})
    assert len(initial)==meta["primary_variables"]
    model=old.witness_tools.complete_assignment(circuit,initial)
    xcnf_check=old.base.check_xcnf(formula,model)
    relation=decode(model,meta,context,qprime,targets)
    assert relation["valid"] and relation["masks"]==control["masks"]
    assert relation["signs"]==control["signs"]
    receipt={"status":"PASS_FULL_FORMULA_AND_GROUP_CONTROL",
             "formula":stats,"phase_seconds":phases,"xcnf_check":xcnf_check,
             "relation":relation,"protocol_sha256":sha(PROTOCOL),
             "control_sha256":sha(CONTROL)}
    save(folder/"receipt.json",receipt)
    print(json.dumps({"status":receipt["status"],"formula":stats}))

def query():
    p=verify_freeze()
    receipt=json.loads((HERE/"preflight/receipt.json").read_text())
    assert receipt["status"]=="PASS_FULL_FORMULA_AND_GROUP_CONTROL"
    folder=HERE/"public"
    folder.mkdir(exist_ok=False)
    context=setup()
    online_start=time.monotonic()
    qprime=qprime_of(context,context["q"])
    transport=time.monotonic()-online_start
    circuit,meta,targets,formula,stats,phases=build_formula(folder,context,qprime)
    build_wall=time.monotonic()-online_start
    remaining=p["online_cap_seconds"]-build_wall-1
    if remaining<=2:
        raise TimeoutError("formula build exhausted online cap")
    solver_cap=min(p["solver_parent_wall_cap_seconds"],remaining)
    command=[str(SOLVER),*p["solver_flags"],
             f"--maxtime={max(1,int(solver_cap)-2)}",str(formula)]
    stdout_path,stderr_path=folder/"solver.stdout.txt",folder/"solver.stderr.txt"
    parent=psutil.Process(os.getpid())
    peak_rss=peak_cpu=0
    stop_reason=None
    with stdout_path.open("xb") as stdout,stderr_path.open("xb") as stderr:
        proc=subprocess.Popen(command,stdout=stdout,stderr=stderr,start_new_session=True)
        child=psutil.Process(proc.pid)
        save(folder/"process.json",{"pid":proc.pid,
             "create_time_epoch":child.create_time(),"command":command,
             "started_utc":datetime.now(timezone.utc).isoformat()})
        solver_start=time.monotonic()
        while proc.poll() is None:
            try:
                cpu=child.cpu_times()
                peak_cpu=max(peak_cpu,cpu.user+cpu.system)
                peak_rss=max(peak_rss,child.memory_info().rss+parent.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss>p["rss_cap_bytes"]:
                stop_reason="RSS_CAP";proc.terminate();break
            if time.monotonic()-online_start>=p["online_cap_seconds"]:
                stop_reason="ONLINE_WALL_CAP";proc.terminate();break
            if time.monotonic()-solver_start>=solver_cap:
                stop_reason="SOLVER_WALL_CAP";proc.terminate();break
            time.sleep(.1)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait()
            stop_reason=(stop_reason or "DRAIN_TIMEOUT")+"_KILLED"
    solver_wall=time.monotonic()-solver_start
    output=stdout_path.read_text(errors="replace")
    statuses=[line for line in output.splitlines() if line.startswith("s ")]
    model_lines=sum(line.startswith("v ") for line in output.splitlines())
    relation=xcnf_check=None
    replay=0.0
    if statuses==["s SATISFIABLE"] and model_lines:
        began=time.monotonic()
        model=old.base.read_model(output,stats["variables"])
        xcnf_check=old.base.check_xcnf(formula,model)
        relation=decode(model,meta,context,qprime,targets)
        replay=time.monotonic()-began
        status="SAT_MODEL_PENDING_INDEPENDENT_SAGE" if relation["valid"] else "INVALID_MODEL"
    elif statuses==["s UNSATISFIABLE"]:
        status="UNSAT_FORMULA"
    elif stop_reason in ("ONLINE_WALL_CAP","SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status="CENSORED_TIME"
    elif stop_reason=="RSS_CAP":
        status="OOM"
    else:
        status="PRODUCER_OR_SOLVER_FAILURE"
    result={"kind":"n41_w5_ten_source_public_query","status":status,
            "proposal_id":p["proposal_id"],"candidate_id":None,"run_id":None,
            "curve_id":p["curve_id"],"target_count":1,
            "public_target_q":list(context["q"]),"transported_target_qprime":list(qprime),
            "formula":stats,"solver_status_lines":statuses,"model_lines":model_lines,
            "solver_command":command,"solver_exit_code":proc.returncode,
            "stop_reason":stop_reason,
            "phase_seconds":{"target_transport":transport,**phases,"solver":solver_wall,
                             "producer_relation_check":replay,
                             "online_wall":time.monotonic()-online_start},
            "sampled_peak_combined_rss_bytes":peak_rss,
            "sampled_solver_cpu_seconds":peak_cpu,
            "producer_xcnf_check":xcnf_check,"producer_relation":relation,
            "verified_relations":0,"useful_rank":0,
            "source_sha256":{"protocol":sha(PROTOCOL),"formula":sha(formula),
                             "stdout":sha(stdout_path),"stderr":sha(stderr_path),
                             "process":sha(folder/"process.json")}}
    save(folder/"result.json",result)
    print(json.dumps({"status":status,"online_wall_seconds":result["phase_seconds"]["online_wall"],
                      "formula":stats}))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("freeze","preflight","query"))
    {"freeze":freeze,"preflight":preflight,"query":query}[parser.parse_args().mode]()
