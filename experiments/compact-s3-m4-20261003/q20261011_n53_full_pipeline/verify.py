#!/usr/bin/env python3
"""Independently replay Q1457 generator relations and solve folded logs."""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
PAIR = PARENT / "q20261011_n53_native_pair"
sys.path.insert(0,str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0,str(ROOT / "experiments/koblitz-pair-claw-20260929"))
import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_points(path: Path) -> list[tuple[int,int]]:
    raw = path.read_bytes()
    assert len(raw)%32 == 0
    return [(int.from_bytes(raw[i:i+16],"little"),
             int.from_bytes(raw[i+16:i+32],"little"))
            for i in range(0,len(raw),32)]


def rref_solve(rows: list[list[int]],rhs: list[int],columns: int,r: int) -> tuple[int,list[int]|None]:
    work = [[*row,value] for row,value in zip(rows,rhs)]
    rank = 0
    pivots = []
    for col in range(columns):
        pivot = next((i for i in range(rank,len(work)) if work[i][col]%r),None)
        if pivot is None: continue
        work[rank],work[pivot] = work[pivot],work[rank]
        inverse = pow(work[rank][col],-1,r)
        work[rank] = [v*inverse%r for v in work[rank]]
        for i in range(len(work)):
            if i==rank:continue
            factor = work[i][col]
            if factor:
                work[i] = [(a-factor*b)%r for a,b in zip(work[i],work[rank])]
        pivots.append(col)
        rank += 1
        if rank == columns:break
    for row in work[rank:]:
        assert any(row[:-1]) or row[-1] == 0, "inconsistent relation equations"
    if rank < columns:return rank,None
    logs = [0]*columns
    for i,col in enumerate(pivots):logs[col] = work[i][-1]
    assert all(sum(a*b for a,b in zip(row,logs))%r==value
               for row,value in zip(rows,rhs))
    return rank,logs


def main() -> None:
    out = HERE / "independent_replay.json"
    assert not out.exists()
    started = time.perf_counter_ns()
    protocol = json.loads((HERE / "protocol.json").read_text())
    measured = json.loads((HERE / "native_measurement.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    exported = json.loads((PAIR / "export_receipt.json").read_text())
    assert measured["freeze_sha256"] == sha(HERE / "freeze.json")
    assert measured["raw_sha256"] == sha(HERE / "native_raw.json")
    assert freeze["q1454_export_receipt_sha256"] == sha(PAIR / "export_receipt.json")
    assert measured["curve_id"] == protocol["curve_id"] == exported["curve_id"]
    assert measured["factor_base_enumerated_set_sha256"] == protocol["factor_base_enumerated_set_sha256"]
    assert measured["status"] == "completed_query_cap"
    base = read_points(PAIR / "inputs/base.bin")
    assert len(base) == protocol["factor_base_actual_B"]
    assert len(set(base)) == len(base)
    assert sha(PAIR / "inputs/base.bin") == freeze["base_input_sha256"]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    quotient = OrbitKey(onb)
    generator = tuple(protocol["generator_onb_xy"])
    r = protocol["subgroup_order"]
    eigen = protocol["frobenius_eigenvalue_mod_r"]
    assert curve.onCurve(generator) and curve.mul(generator,r) is None
    with gzip.open(PARENT / "bases/n53_weight3_orbits.json.gz","rt") as stream:
        archive = json.load(stream)
    factor = archive["factor_base"]
    packed = base64.b64decode(factor["packed_canonical_x_keys_base64"])
    assert hashlib.sha256(packed).hexdigest() == protocol["factor_base_enumerated_set_sha256"]
    keys = [int.from_bytes(packed[i:i+7],"little") for i in range(0,len(packed),7)]
    representatives = []
    point_to_column = {}
    for col,(key,length) in enumerate(zip(keys,factor["orbit_lengths"])):
        representative = curve.pointFromX(onb.fromCoords(key))
        assert representative is not None
        representatives.append(representative)
        for exponent in range(length):
            positive = curve.frob(representative,exponent)
            negative = curve.neg(positive)
            coeff = pow(eigen,exponent,r)
            assert positive not in point_to_column and negative not in point_to_column
            point_to_column[positive] = col,coeff
            point_to_column[negative] = col,-coeff%r
    assert len(keys)==protocol["factor_base_folded_columns_K"]
    assert set(point_to_column)==set(base)
    base_rebuild_ns = time.perf_counter_ns()-started
    rows = []
    rhs = []
    row_set = set()
    relations = []
    canceled = 0
    checkpoint_results = {}
    checkpoint_rank_ns = 0
    checkpoints = protocol["point_decomposition"]["query_checkpoints"]
    pending = iter(checkpoints)
    next_checkpoint = next(pending,None)
    for match in measured["matches"]:
        query,ordinal,tfirst,tsecond,qfirst,qsecond,texp,qexp,tsign,qsign = match
        while next_checkpoint is not None and query>next_checkpoint:
            rank_started = time.perf_counter_ns()
            rank,_ = rref_solve(rows,rhs,len(keys),r)
            checkpoint_rank_ns += time.perf_counter_ns()-rank_started
            checkpoint_results[str(next_checkpoint)] = {
                "verified_relations":len(relations), "distinct_rows":len(row_set),
                "rank":rank}
            next_checkpoint = next(pending,None)
        assert 1<=query<=measured["query_samples_processed"]
        assert 1<=ordinal<=measured["table_states_generated"]
        assert all(0<=index<len(base) for index in (tfirst,tsecond,qfirst,qsecond))
        table_point = curve.add(base[tfirst],base[tsecond])
        query_point = curve.add(base[qfirst],base[qsecond])
        assert table_point is not None and query_point is not None
        complement = curve.add(generator,curve.neg(query_point))
        assert complement is not None
        key0,exp0,sign0 = quotient.canonical(table_point)
        key1,exp1,sign1 = quotient.canonical(complement)
        assert key0==key1 and (texp,tsign)==(exp0,sign0)
        assert (qexp,qsign)==(exp1,sign1)
        shift=(texp-qexp)%53
        sign=tsign*qsign
        left=[curve.frob(base[tfirst],shift),curve.frob(base[tsecond],shift)]
        if sign<0:left=[curve.neg(point) for point in left]
        points=left+[base[qfirst],base[qsecond]]
        assert all(point in point_to_column and curve.onCurve(point)
                   and curve.mul(point,r) is None for point in points)
        canceled += any(points[i]==curve.neg(points[j])
                        for i in range(4) for j in range(i))
        total=None
        row=[0]*len(keys)
        for point in points:
            total=curve.add(total,point)
            col,coeff=point_to_column[point]
            row[col]=(row[col]+coeff)%r
        assert total==generator
        rows.append(row);rhs.append(1);row_set.add(tuple(row))
        relations.append({"query_number":query,"table_state_ordinal":ordinal,
                          "points":[[x,y] for x,y in points]})
    while next_checkpoint is not None:
        rank_started = time.perf_counter_ns()
        rank,_ = rref_solve(rows,rhs,len(keys),r)
        checkpoint_rank_ns += time.perf_counter_ns()-rank_started
        checkpoint_results[str(next_checkpoint)] = {
            "verified_relations":len(relations),"distinct_rows":len(row_set),
            "rank":rank}
        next_checkpoint=next(pending,None)
    relations_finished_ns = time.perf_counter_ns()
    final_la_started = relations_finished_ns
    rank,logs = rref_solve(rows,rhs,len(keys),r)
    final_la_ns = time.perf_counter_ns()-final_la_started
    assert checkpoint_results[str(checkpoints[-1])]["rank"]==rank
    log_replays=0
    log_replay_started = time.perf_counter_ns()
    if logs is not None:
        for representative,log in zip(representatives,logs):
            assert curve.mul(generator,log)==representative
            log_replays+=1
    log_replay_ns = time.perf_counter_ns()-log_replay_started
    replay_ns=time.perf_counter_ns()-started-base_rebuild_ns
    relation_replay_and_matrix_build_ns=(relations_finished_ns-started-
        base_rebuild_ns-checkpoint_rank_ns)
    output={"status":"PASS","proposal_id":"Q1457","candidate_id":None,
            "run_id":None,"curve_id":protocol["curve_id"],"isogeny":"none",
            "factor_base_actual_B":len(base),
            "factor_base_folded_columns_K":len(keys),
            "factor_base_enumerated_set_sha256":hashlib.sha256(packed).hexdigest(),
            "measurement_sha256":sha(HERE / "native_measurement.json"),
            "source_sha256":sha(Path(__file__)),
            "setup_generator_onb_xy":list(generator),
            "verified_relation_occurrences":len(relations),
            "distinct_quotient_rows":len(row_set),
            "cancellation_occurrences":canceled,
            "matrix_rank":rank,"rank_goal":len(keys),
            "rank_checkpoints":checkpoint_results,
            "factor_base_log_status":"solved_and_replayed" if logs is not None else "rank_incomplete",
            "factor_base_logs":logs,
            "replayed_log_columns":log_replays,
            "relations":relations,
            "base_rebuild_ns":base_rebuild_ns,
            "relation_replay_and_matrix_build_ns":relation_replay_and_matrix_build_ns,
            "checkpoint_rank_ns":checkpoint_rank_ns,
            "final_relation_LA_ns":final_la_ns,
            "factor_base_log_replay_ns":log_replay_ns,
            "relation_replay_and_matrix_ns":replay_ns}
    out.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print("PASS Q1457",len(relations),rank,"/",len(keys),output["factor_base_log_status"])


if __name__=="__main__":main()
