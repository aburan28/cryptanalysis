#!/usr/bin/env python3
"""Collect rank-novel known-scalar W6 relations before one-target recovery."""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent / "n41_upper_xor_projection_20261010"
HELPER=HERE.parent / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
NATIVE=HERE / "join"
PROTOCOL=HERE / "protocol.json"
R=549756390943
K=26


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block:=stream.read(1<<20):
            digest.update(block)
    return digest.hexdigest()


def save(path,value):
    with Path(path).open("x") as out:
        json.dump(value,out,indent=2,sort_keys=True)
        out.write("\n")


def sources():
    return {"collector":Path(__file__),"join_source":HERE / "join.cpp",
            "join_binary":NATIVE,"helper":HELPER,
            "bootstrap":HERE / "bootstrap.py",
            "workload":HERE / "workload.json",
            "runtime":HERE / "sage_runtime_info.json",
            "atom_input":SOURCE / "w6_input.txt"}


def freeze():
    workload=json.loads((HERE / "workload.json").read_text())
    assert workload["status"]=="FROZEN_N41_W6_ORBIT_COLUMNS_AND_SETUP_TARGETS"
    assert workload["subgroup_order"]==R and workload["folded_columns_K"]==K
    assert len(workload["setup_targets"])==128
    record={"status":"FROZEN_BEFORE_N41_W6_FACTOR_LOG_COLLECTION",
            "curve_id":workload["curve_id"],"subgroup_order":R,
            "target_count_setup":len(workload["setup_targets"]),
            "max_accepted_probes_per_query":20000000,
            "native_online_cap_seconds":20,
            "parent_process_wall_cap_seconds":30,
            "rss_cap_bytes":4*1024**3,
            "workers":1,"rng_seed_base":202610101000,
            "stop_at_rank":K,
            "input_law":"known-scalar setup points from frozen SHA-256 seed, distinct from one held-out published point",
            "source_sha256":{name:sha(path) for name,path in sources().items()}}
    save(PROTOCOL,record)
    print(json.dumps({"status":record["status"],"target_count_setup":record["target_count_setup"]}))


def rank_insert(pivots,coefficients,rhs):
    row=[value%R for value in coefficients]+[rhs%R]
    for pivot in sorted(pivots):
        factor=row[pivot]
        if factor:
            basis=pivots[pivot]
            row=[(value-factor*other)%R for value,other in zip(row,basis)]
    first=next((i for i,value in enumerate(row[:K]) if value),None)
    if first is None:
        if row[K]:
            raise ValueError("dependent relation has inconsistent known scalar")
        return False
    inverse=pow(row[first],-1,R)
    pivots[first]=[(value*inverse)%R for value in row]
    return True


def solve(pivots,rows):
    if set(pivots)!=set(range(K)):
        raise ValueError("relation matrix has incomplete rank")
    logs=[0]*K
    for pivot in reversed(range(K)):
        row=pivots[pivot]
        logs[pivot]=(row[K]-sum(row[j]*logs[j] for j in range(pivot+1,K)))%R
    for item in rows:
        if item.get("coefficients_mod_r") is not None:
            assert sum(a*b for a,b in zip(item["coefficients_mod_r"],logs))%R==item["scalar"]%R
    return logs


def collect():
    protocol=json.loads(PROTOCOL.read_text())
    assert protocol["status"]=="FROZEN_BEFORE_N41_W6_FACTOR_LOG_COLLECTION"
    assert protocol["source_sha256"]=={name:sha(path) for name,path in sources().items()}
    workload=json.loads((HERE / "workload.json").read_text())
    atom_map={(a["block"],a["mask"],a["sign"]):a for a in workload["atoms"]}
    assert len(atom_map)==384
    template=(SOURCE / "w6_input.txt").read_text().splitlines(keepends=True)
    assert len(template)>1
    runs=HERE / "runs"
    runs.mkdir(exist_ok=False)
    pivots={}
    rows=[]
    started=time.monotonic()
    total_native_setup_ns=total_native_online_ns=0
    for target in workload["setup_targets"]:
        index=target["index"]
        folder=runs / f"{index:03d}"
        folder.mkdir(exist_ok=False)
        q=target["point"]
        input_path=folder / "input.txt"
        input_path.write_text(f"{q[0]} {q[1]} {R} 6\n"+"".join(template[1:]))
        hit_path,result_path=folder / "hit.json",folder / "native_result.json"
        stdout_path,stderr_path=folder / "stdout.txt",folder / "stderr.txt"
        seed=protocol["rng_seed_base"]+index
        command=[str(NATIVE),str(input_path),str(hit_path),str(result_path),
                 str(protocol["max_accepted_probes_per_query"]),
                 str(protocol["native_online_cap_seconds"]),str(seed)]
        begin=time.monotonic()
        timed_out=False
        with stdout_path.open("xb") as stdout,stderr_path.open("xb") as stderr:
            try:
                result=subprocess.run(command,stdout=stdout,stderr=stderr,
                                      timeout=protocol["parent_process_wall_cap_seconds"],
                                      check=False,start_new_session=True)
                exit_code=result.returncode
            except subprocess.TimeoutExpired:
                timed_out=True
                exit_code=None
        process_wall=time.monotonic()-begin
        row={"index":index,"scalar":target["scalar"],"target_q":q,
             "rng_seed":seed,"native_command":command,"exit_code":exit_code,
             "parent_timeout":timed_out,"process_wall_seconds":process_wall,
             "input_sha256":sha(input_path),"stdout_sha256":sha(stdout_path),
             "stderr_sha256":sha(stderr_path),
             "rank_before":len(pivots)}
        if result_path.exists() and exit_code==0:
            native=json.loads(result_path.read_text())
            row["native_status"]=native["status"]
            row["native_result_sha256"]=sha(result_path)
            row["native_setup_ns"]=native["setup_ns"]
            row["native_online_ns"]=native["online_ns"]
            row["peak_rss_bytes"]=native["peak_rss_bytes"]
            total_native_setup_ns+=native["setup_ns"]
            total_native_online_ns+=native["online_ns"]
            assert native["peak_rss_bytes"]<protocol["rss_cap_bytes"]
            if native["status"]=="FOUND_PENDING_SAGE_REPLAY":
                hit=json.loads(hit_path.read_text())
                assert hit["status"]=="NATIVE_RELATION_PENDING_SAGE"
                assert hit["raw_sum"]==q and len(set(hit["columns"]))==12
                assert hit["seed_sums"][2]==hit["seed_sums"][3]
                assert hit["seed_sums"][4]==hit["seed_sums"][5]
                vector=[0]*K
                for slot,(mask,sign,column) in enumerate(zip(hit["masks"],hit["signs"],hit["columns"])):
                    atom=atom_map[(slot//2,mask,sign)]
                    assert atom["column"]==column
                    vector[column]=(vector[column]+atom["coefficient_mod_r"])%R
                row["coefficients_mod_r"]=vector
                row["hit_sha256"]=sha(hit_path)
                row["novel_rank"]=rank_insert(pivots,vector,target["scalar"])
            else:
                row["coefficients_mod_r"]=None
                row["novel_rank"]=False
        else:
            row["native_status"]="PARENT_TIMEOUT" if timed_out else "PRODUCER_FAILURE"
            row["coefficients_mod_r"]=None
            row["novel_rank"]=False
        row["rank_after"]=len(pivots)
        rows.append(row)
        with (HERE / "rows.jsonl").open("a") as out:
            out.write(json.dumps(row,sort_keys=True)+"\n")
        print(json.dumps({"index":index,"native_status":row["native_status"],
                          "rank":len(pivots),"novel":row["novel_rank"],
                          "process_wall_seconds":process_wall}),flush=True)
        if len(pivots)==K:
            break
    collection_wall=time.monotonic()-started
    status="FULL_RANK_FACTOR_LOGS_PENDING_SAGE_REPLAY" if len(pivots)==K else "PARTIAL_RANK"
    if len(pivots)==K:
        logs=solve(pivots,rows)
        save(HERE / "factor_logs.json",{"status":status,"curve_id":workload["curve_id"],
             "modulus":R,"folded_columns_K":K,"logs_mod_r":logs,
             "representatives":workload["representatives"],
             "source_sha256":{"protocol":sha(PROTOCOL),"rows":sha(HERE / "rows.jsonl")}})
    summary={"status":status,"candidate_id":None,"curve_id":workload["curve_id"],
             "setup_targets_available":len(workload["setup_targets"]),
             "attempted_queries":len(rows),"verified_producer_relations":sum(
                 row["native_status"]=="FOUND_PENDING_SAGE_REPLAY" for row in rows),
             "novel_rows":len(pivots),"final_rank":len(pivots),"columns":K,
             "collection_process_wall_seconds":collection_wall,
             "native_setup_seconds":total_native_setup_ns/1e9,
             "native_online_query_seconds":total_native_online_ns/1e9,
             "source_sha256":{"protocol":sha(PROTOCOL),"workload":sha(HERE / "workload.json"),
                              "rows":sha(HERE / "rows.jsonl")}}
    save(HERE / "collection_result.json",summary)
    print(json.dumps({"status":status,"attempted_queries":len(rows),
                      "rank":len(pivots),"process_wall_seconds":collection_wall}))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("freeze","collect"))
    {"freeze":freeze,"collect":collect}[parser.parse_args().mode]()
