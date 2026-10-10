#!/usr/bin/env python3
"""Build and verify a source-frozen N131 seven-summand control XCNF."""
import gzip
import hashlib
import itertools
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

import psutil
import run as n41
import n131_circuit as method

here = Path(__file__).resolve().parent
protocol_path = here / "n131_formula_protocol.json"
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def source_paths():
    return {"n131_circuit":here/"n131_circuit.py",
            "n131_preparation":here/"n131_preparation.json",
            "support":here/"support_w19.tsv",
            "support_audit":here/"sage_support_audit.json",
            "prior_n41_protocol":here/"protocol.json",
            "official_params":Path("/Volumes/SSD990/crypto/docs/ic/params/ecc2k130-fixed.json"),
            "runtime":here/"sage_runtime_info.json",
            "builder":Path(__file__)}


def verified_protocol():
    protocol = json.loads(protocol_path.read_text())
    if (protocol["status"] != "FROZEN_BEFORE_CONSTRUCTION" or
            protocol["source_sha256"] != {k:sha(p) for k,p in source_paths().items()}):
        raise ValueError("N131 control source or input drift")
    return protocol


def save(path,value):
    with path.open("x") as out:
        json.dump(value,out,indent=2,sort_keys=True)
        out.write("\n")


def worker():
    protocol=verified_protocol()
    began=time.monotonic()
    prep=json.loads((here/"n131_preparation.json").read_text())
    control=prep["control"]
    valid={}
    groups={}
    for line in (here/"support_w19.tsv").open():
        mask,canonical=map(int,line.split())
        valid[mask]=canonical
        groups.setdefault(canonical,[]).append(mask)
    aliases=sorted(tuple(sorted(pair)) for row in groups.values() if len(row)>1
                   for pair in itertools.combinations(row,2))
    if len(valid)!=262390 or len(groups)!=262151 or len(aliases)!=243:
        raise ValueError("W19 support or alias count changed")
    loaded=time.monotonic()
    circuit=n41.old.base.KaratsubaCircuit(131,[0,1,2,13])
    meta=method.build(circuit,prep["bases_u"],set(valid),aliases,
                      control["target_preimages_u"])
    built=time.monotonic()
    raw=Path(protocol["raw_formula_scratch"])
    if raw.exists():
        raise FileExistsError(raw)
    circuit.write(raw)
    emitted=time.monotonic()
    initial={}
    for row,mask in zip(meta["masks"],control["masks"]):
        initial.update({wire:mask>>bit&1 for bit,wire in enumerate(row)})
    for i,wire in enumerate(meta["flags"]):
        initial[wire]=int(i==control["target_preimage_index"])
    for row,value in zip(meta["middle"],control["middle_u"]):
        initial.update({wire:value>>bit&1 for bit,wire in enumerate(row)})
    if len(initial)!=meta["primary_variables"]:
        raise ValueError("control primary assignment incomplete")
    model=n41.old.witness_tools.complete_assignment(circuit,initial)
    check=n41.old.base.check_xcnf(raw,model)
    checked=time.monotonic()
    compressed=here/protocol["compressed_formula"]
    with compressed.open("xb") as output:
        with gzip.GzipFile(filename="",mode="wb",fileobj=output,
                           compresslevel=6,mtime=0) as zipped:
            with raw.open("rb") as source:
                for block in iter(lambda:source.read(1<<20),b""):
                    zipped.write(block)
    raw_sha=sha(raw)
    digest=hashlib.sha256()
    with gzip.open(compressed,"rb") as stream:
        for block in iter(lambda:stream.read(1<<20),b""):
            digest.update(block)
    if digest.hexdigest()!=raw_sha:
        raise ValueError("compressed formula replay hash mismatch")
    raw_size=raw.stat().st_size
    raw.unlink()
    completed=time.monotonic()
    result={"kind":"n131_w19_seven_linear_source_control_formula",
            "status":"PASS_FULL_FORMULA_CONTROL",
            "proposal_id":protocol["proposal_id"],"candidate_id":None,"run_id":None,
            "curve_id":protocol["curve_id"],"target_count":1,
            "factor_base_B":protocol["B"],"folded_columns_K":protocol["K"],
            "formula":{"variables":circuit.next_var-1,
                       "clauses":len(circuit.clauses),"xor_rows":len(circuit.xors),
                       "and_gates":circuit.and_count,"bytes":raw_size,
                       "sha256":raw_sha,"compressed_bytes":compressed.stat().st_size,
                       "compressed_sha256":sha(compressed),
                       "invalid_mask_clauses":meta["invalid_mask_clauses"],
                       "same_mask_clauses":meta["same_mask_clauses"],
                       "alias_clauses":meta["alias_clauses"]},
            "xcnf_check":check,"control_masks":control["masks"],
            "phase_seconds":{"load_support":loaded-began,"construct":built-loaded,
                             "serialize":emitted-built,"assignment_check":checked-emitted,
                             "compress_verify":completed-checked,"wall":completed-began},
            "self_peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "source_sha256":{"protocol":sha(protocol_path),
                             "preparation":sha(here/"n131_preparation.json"),
                             "support":sha(here/"support_w19.tsv"),
                             "builder":sha(Path(__file__))}}
    save(here/"n131_control_result.json",result)
    print(json.dumps({"status":result["status"],"formula":result["formula"],
                      "wall_seconds":result["phase_seconds"]["wall"]}))


def supervise():
    protocol=verified_protocol()
    stdout=here/"n131_control.stdout.txt"
    stderr=here/"n131_control.stderr.txt"
    began=time.monotonic()
    with stdout.open("xb") as out,stderr.open("xb") as err:
        child=subprocess.Popen([sys.executable,str(Path(__file__)),"worker"],
                               stdout=out,stderr=err,start_new_session=True)
        process=psutil.Process(child.pid)
        save(here/"n131_control_process.json",{"pid":child.pid,
             "create_time_epoch":process.create_time(),
             "command":[sys.executable,str(Path(__file__)),"worker"]})
        peak=0
        stop=None
        while child.poll() is None:
            try:
                peak=max(peak,process.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak>protocol["control_rss_cap_bytes"]:
                stop="RSS_CAP"
                child.terminate()
                break
            if time.monotonic()-began>protocol["control_build_cap_seconds"]:
                stop="WALL_CAP"
                child.terminate()
                break
            time.sleep(.1)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            stop=(stop or "DRAIN_TIMEOUT")+"_KILLED"
    terminal={"kind":"n131_control_build_supervisor",
              "status":"PASS" if child.returncode==0 and stop is None else "FAILED",
              "exit_code":child.returncode,"stop_reason":stop,
              "wall_seconds":time.monotonic()-began,"sampled_peak_rss_bytes":peak,
              "source_sha256":{"protocol":sha(protocol_path),
                               "stdout":sha(stdout),"stderr":sha(stderr),
                               "process":sha(here/"n131_control_process.json")}}
    save(here/"n131_control_terminal.json",terminal)
    print(json.dumps(terminal))
    if terminal["status"]!="PASS":
        raise SystemExit(1)


if __name__=="__main__":
    if len(sys.argv)!=2 or sys.argv[1] not in ("worker","run"):
        raise SystemExit("usage: n131_build_control.py run|worker")
    {"worker":worker,"run":supervise}[sys.argv[1]]()
