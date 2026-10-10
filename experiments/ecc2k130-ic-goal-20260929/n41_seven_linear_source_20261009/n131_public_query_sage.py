#!/usr/bin/env sage -python
"""Bounded one-point ECC2K-130 query with exact seven-source XCNF."""
import gzip
import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0,str(ROOT))
import run_n41_disjoint_s5_sat as base
import check_n41_lowpower_w8_s6_witness as witness_tools
sys.path.insert(0,str(HERE))
import n131_circuit as method

PARAMS = Path("/Volumes/SSD990/crypto/docs/ic/params/ecc2k130-fixed.json")
PROTOCOL = HERE / "n131_public_protocol.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1<<20),b""):
            digest.update(block)
    return digest.hexdigest()


def save(path,value):
    with path.open("x") as out:
        json.dump(value,out,indent=2,sort_keys=True)
        out.write("\n")


def paths():
    return {"runner":Path(__file__),"circuit":HERE/"n131_circuit.py",
            "preparation":HERE/"n131_preparation.json",
            "support":HERE/"support_w19.tsv",
            "support_audit":HERE/"sage_support_audit.json",
            "control_result":HERE/"n131_control_result.json",
            "control_terminal":HERE/"n131_control_terminal.json",
            "control_audit":HERE/"n131_control_audit.json",
            "params":PARAMS,"runtime":HERE/"sage_runtime_info.json",
            "solver":SOLVER,"base":Path(base.__file__),
            "witness":Path(witness_tools.__file__)}


def verify_protocol():
    protocol=json.loads(PROTOCOL.read_text())
    if (protocol["status"]!="FROZEN_BEFORE_PUBLIC_QUERY" or
            protocol["source_sha256"]!={name:sha(path) for name,path in paths().items()}):
        raise ValueError("public query source or input drift")
    control=json.loads((HERE/"n131_control_result.json").read_text())
    if (control["status"]!="PASS_FULL_FORMULA_CONTROL" or
            json.loads((HERE/"n131_control_terminal.json").read_text())["status"]!="PASS" or
            json.loads((HERE/"n131_control_audit.json").read_text())["status"]!="PASS_EXACT_GROUP_AND_ARCHIVED_XCNF_CONTROL" or
            json.loads((HERE/"sage_runtime_info.json").read_text())["status"]!="verified"):
        raise ValueError("control or checked Sage runtime missing")
    return protocol


def setup():
    prep=json.loads((HERE/"n131_preparation.json").read_text())
    params=json.loads(PARAMS.read_text())
    support={}
    groups={}
    for line in (HERE/"support_w19.tsv").open():
        mask,canonical=map(int,line.split())
        support[mask]=canonical
        groups.setdefault(canonical,[]).append(mask)
    aliases=sorted(tuple(sorted(pair)) for row in groups.values() if len(row)>1
                   for pair in itertools.combinations(row,2))
    if len(support)!=262390 or len(groups)!=262151 or len(aliases)!=243:
        raise ValueError("W19 support changed")
    ring=PolynomialRing(GF(2),"t")
    t=ring.gen()
    field=GF(2**131,name="t",modulus=t**131+t**13+t**2+t+1)
    curve=EllipticCurve(field,[1,0,0,0,1])
    R=int(params["curve"]["subgroup_order"])
    lam=int(prep["frobenius_eigenvalue_mod_r"])
    if (lam*lam+lam+2)%R or pow(lam,131,R)!=1:
        raise ValueError("Frobenius eigenvalue changed")
    def decode(value):
        value=int(value,0) if isinstance(value,str) else int(value)
        return field(ring([(value>>i)&1 for i in range(131)]))
    def encode(value):
        return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))
    def point(values):
        return curve(decode(values[0]),decode(values[1]))
    G=point((params["generator"]["x"],params["generator"]["y"]))
    if G==curve(0) or R*G!=curve(0):
        raise ValueError("published subgroup generator changed")
    return {"prep":prep,"params":params,"support":support,"aliases":aliases,
            "field":field,"curve":curve,"R":R,"lambda":lam,
            "decode":decode,"encode":encode,"point":point}


def target_input(context):
    curve,R=context["curve"],context["R"]
    q=context["point"]((context["params"]["targets"][0]["x"],
                          context["params"]["targets"][0]["y"]))
    if q==curve(0) or R*q!=curve(0):
        raise ValueError("published point outside subgroup")
    phi_q=curve(q[0]**2,q[1]**2)
    if phi_q!=context["lambda"]*q:
        raise ValueError("Frobenius eigenvalue fails published point")
    qprime=pow(1+context["lambda"],-1,R)*q
    if qprime+curve(qprime[0]**2,qprime[1]**2)!=q:
        raise ValueError("target transport failed")
    core=pow(4,-1,R)*qprime
    torsion=curve(context["field"].one(),context["field"].zero())
    raw_targets=[core+k*torsion for k in range(4)]
    if any(4*p!=qprime or p[0] in (0,1) for p in raw_targets):
        raise ValueError("invalid cofactor-four target fiber")
    target_us=[context["encode"](1/(p[0]+1)) for p in raw_targets]
    return q,qprime,raw_targets,target_us


def archive(raw,compressed):
    with compressed.open("xb") as output:
        with gzip.GzipFile(filename="",mode="wb",fileobj=output,
                           compresslevel=6,mtime=0) as zipped:
            with raw.open("rb") as source:
                for block in iter(lambda:source.read(1<<20),b""):
                    zipped.write(block)
    expected=sha(raw)
    digest=hashlib.sha256()
    with gzip.open(compressed,"rb") as stream:
        for block in iter(lambda:stream.read(1<<20),b""):
            digest.update(block)
    if digest.hexdigest()!=expected:
        raise ValueError("public XCNF archive roundtrip mismatch")
    return expected


def main():
    protocol=verify_protocol()
    context=setup()
    folder=HERE/"n131_public"
    folder.mkdir(exist_ok=False)
    raw=Path(protocol["raw_formula_scratch"])
    if raw.exists():
        raise FileExistsError(raw)
    online_start=time.monotonic()
    q,qprime,raw_targets,target_us=target_input(context)
    target_seconds=time.monotonic()-online_start
    circuit=base.KaratsubaCircuit(131,[0,1,2,13])
    meta=method.build(circuit,context["prep"]["bases_u"],
                      set(context["support"]),context["aliases"],target_us)
    built=time.monotonic()-online_start
    circuit.write(raw)
    emitted=time.monotonic()-online_start
    compressed=folder/"system.xcnf.gz"
    formula_sha=archive(raw,compressed)
    archived=time.monotonic()-online_start
    formula={"variables":circuit.next_var-1,"clauses":len(circuit.clauses),
             "xor_rows":len(circuit.xors),"and_gates":circuit.and_count,
             "bytes":raw.stat().st_size,"sha256":formula_sha,
             "compressed_bytes":compressed.stat().st_size,
             "compressed_sha256":sha(compressed),
             "invalid_mask_clauses":meta["invalid_mask_clauses"],
             "same_mask_clauses":meta["same_mask_clauses"],
             "alias_clauses":meta["alias_clauses"]}
    parent=psutil.Process(os.getpid())
    peak_rss=parent.memory_info().rss
    if peak_rss>protocol["rss_cap_bytes"]:
        raise MemoryError("formula builder exceeded RSS cap before solver")
    remaining=protocol["online_cap_seconds"]-archived-2
    if remaining<=5:
        raise TimeoutError("formula consumed online cap")
    solver_cap=min(protocol["solver_parent_wall_cap_seconds"],remaining)
    command=[str(SOLVER),*protocol["solver_flags"],
             f"--maxtime={max(1,int(solver_cap)-2)}",str(raw)]
    stdout_path,stderr_path=folder/"solver.stdout.txt",folder/"solver.stderr.txt"
    stop_reason=None
    cpu_peak=0.0
    with stdout_path.open("xb") as stdout,stderr_path.open("xb") as stderr:
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr,start_new_session=True)
        proc=psutil.Process(child.pid)
        save(folder/"process.json",{"pid":child.pid,
             "create_time_epoch":proc.create_time(),"command":command,
             "started_utc":datetime.now(timezone.utc).isoformat()})
        while child.poll() is None:
            try:
                cpu=proc.cpu_times()
                cpu_peak=max(cpu_peak,cpu.user+cpu.system)
                peak_rss=max(peak_rss,proc.memory_info().rss+parent.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss>protocol["rss_cap_bytes"]:
                stop_reason="RSS_CAP"
                child.terminate()
                break
            if time.monotonic()-online_start>=protocol["online_cap_seconds"]:
                stop_reason="ONLINE_WALL_CAP"
                child.terminate()
                break
            if time.monotonic()-online_start-archived>=solver_cap:
                stop_reason="SOLVER_WALL_CAP"
                child.terminate()
                break
            time.sleep(.1)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            stop_reason=(stop_reason or "DRAIN_TIMEOUT")+"_KILLED"
    solver_seconds=time.monotonic()-online_start-archived
    output=stdout_path.read_text(errors="replace")
    statuses=[line for line in output.splitlines() if line.startswith("s ")]
    model_lines=sum(line.startswith("v ") for line in output.splitlines())
    check=None
    model_check_seconds=0.0
    if statuses==["s SATISFIABLE"] and model_lines:
        began_check=time.monotonic()
        model=base.read_model(output,formula["variables"])
        check=base.check_xcnf(raw,model)
        model_check_seconds=time.monotonic()-began_check
        status="SAT_MODEL_PENDING_INDEPENDENT_SAGE"
    elif statuses==["s UNSATISFIABLE"]:
        status="UNSAT_FORMULA"
    elif stop_reason in ("ONLINE_WALL_CAP","SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status="CENSORED_TIME"
    elif stop_reason=="RSS_CAP":
        status="OOM"
    else:
        status="PRODUCER_OR_SOLVER_FAILURE"
    online_wall=time.monotonic()-online_start
    result={"kind":"n131_w19_seven_linear_source_published_point_query",
            "status":status,"proposal_id":protocol["proposal_id"],
            "candidate_id":None,"run_id":None,"target_count":1,
            "curve_id":protocol["curve_id"],
            "public_target_q":[context["encode"](q[0]),context["encode"](q[1])],
            "transported_target_qprime":[context["encode"](qprime[0]),
                                         context["encode"](qprime[1])],
            "factor_base_B":protocol["B"],"folded_columns_K":protocol["K"],
            "formula":formula,"solver_command":command,
            "solver_exit_code":child.returncode,"solver_status_lines":statuses,
            "model_lines":model_lines,"stop_reason":stop_reason,
            "phase_seconds":{"target_validation_and_transport":target_seconds,
                             "target_formula_construction":built-target_seconds,
                             "target_formula_serialization":emitted-built,
                             "target_formula_archive":archived-emitted,
                             "solver":solver_seconds,
                             "producer_model_check":model_check_seconds,
                             "online_wall":online_wall},
            "sampled_peak_combined_rss_bytes":peak_rss,
            "sampled_solver_cpu_seconds":cpu_peak,
            "producer_xcnf_check":check,
            "verified_relations":0,"useful_rank":0,
            "source_sha256":{"protocol":sha(PROTOCOL),
                             "formula_archive":sha(compressed),
                             "stdout":sha(stdout_path),"stderr":sha(stderr_path),
                             "process":sha(folder/"process.json")}}
    save(folder/"result.json",result)
    raw.unlink()
    print(json.dumps({"status":status,"online_wall_seconds":online_wall,
                      "formula":formula,"peak_rss_bytes":peak_rss}))


if __name__=="__main__":
    main()
