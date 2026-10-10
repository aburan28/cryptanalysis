"""Terminal hash, status, and work-projection audit for the joint screens."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def read(path):return json.loads(path.read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


ROTATED=BASE/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json"
N41_SCREEN=BASE/"n41_n131_diagonal_atom_20261010/screen.json"
N41_HIT=BASE/"n131_w15_cross_block_seed_offset_20261010/n41_hit.json"
N131=BASE/"n131_w15_coupled_sixpair_20261010"
sources={"joint.py":HERE/"joint.py","result.json":HERE/"result.json",
    "screen.py":HERE/"screen.py","dual_screen.py":HERE/"dual_screen.py",
    "dual_replay.py":HERE/"dual_replay.py",
    "dual_result.json":HERE/"dual_result.json",
    "restricted_control.py":HERE/"restricted_control.py",
    "restricted_result.json":HERE/"restricted_result.json",
    "restricted_audit.py":HERE/"restricted_audit.py",
    "rotated_resultant":ROTATED,"n41_screen":N41_SCREEN,"n41_hit":N41_HIT,
    "n131_lift":N131/"control_group_lift.json",
    "w15_lift.py":N131/"w15_lift.py",
    "support_w15.tsv":N131/"support_w15.tsv",
    "control_group_lift.json":N131/"control_group_lift.json",
    "sage_runtime_info":HERE/"sage_runtime_info.json"}
protocols=("protocol_v2.json","screen_protocol.json","dual_protocol.json",
    "replay_protocol.json","restricted_protocol.json","restricted_audit_protocol.json")
for name in protocols:
    protocol=read(HERE/name)
    frozen=protocol.get("sha256",protocol.get("source_sha256"))
    assert frozen and all(sources[key].exists() and sha(sources[key])==value
                          for key,value in frozen.items()),name

v1=read(HERE/"receipt_v1.json")
v2=read(HERE/"receipt_v2.json")
failure=read(HERE/"failure_v1.json")
assert v1["exit_code"]==1 and failure["status"]=="PRODUCER_FAILURE_CONTROL_POLICY_MISMATCH"
assert failure["receipt_sha256"]==sha(HERE/"receipt_v1.json")
assert v2["status"]=="PROCESS_COMPLETE" and v2["exit_code"]==0
assert v2["result_sha256"]==sha(HERE/"result.json")
assert v2["protocol_sha256"]==sha(HERE/"protocol_v2.json")

joint=read(HERE/"result.json")
assert joint["status"]=="PASS_JOINT_BLOCK_RESULTANT_CONTROLS"
assert [row["joint_gcd_degree"] for row in joint["n41"]["branches"]]==[0,0,1,0]
assert [row["joint_gcd_degree"] for row in joint["n131"]["branches"]]==[0,0,1,0]
screen=read(HERE/"screen_result.json")
assert screen["protocol_sha256"]==sha(HERE/"screen_protocol.json")
assert screen["status"]=="COMPLETE_N41_JOINT_PRODUCT_FAMILY_SCREEN"
assert [row["families_checked"] for row in screen["rows"]]==[1024]*4
assert [row["survivors"] for row in screen["rows"]]==[0,0,1,0]
dual=read(HERE/"dual_result.json")
assert dual["protocol_sha256"]==sha(HERE/"dual_protocol.json")
assert dual["status"]=="COMPLETE_N41_DUAL_PRODUCT_SCREEN"
assert dual["first_block"]["families"]==dual["second_block"]["families"]==1024
assert [row["output_pair_count"] for row in dual["rows"]]==[0,0,1,0]
assert [row["product_family_pair_count"] for row in dual["rows"]]==[0,0,1,0]
replay=read(HERE/"replay_result.json")
assert replay["protocol_sha256"]==sha(HERE/"replay_protocol.json")
assert replay["status"]=="PASS_N41_DUAL_PRODUCT_SOURCE_REPLAY"
assert [row["verified_reconstruction_count"] for row in replay["rows"]]==[0,0,1,0]
assert len(set(replay["rows"][2]["witnesses"][0]["columns"]))==12

restricted=read(HERE/"restricted_result.json")
assert restricted["protocol_sha256"]==sha(HERE/"restricted_protocol.json")
assert restricted["status"]=="PASS_N131_OFFSET_THREE_CONSTRUCTED_JOINT_BLOCK_CONTROL"
assert restricted["cross_block_seed_offset"]==3
assert len(set(restricted["folded_columns"]))==12
assert [row["joint_gcd_degree"] for row in restricted["branches"]]==[0,0,1,0]
audit=read(HERE/"restricted_audit_result.json")
assert audit["protocol_sha256"]==sha(HERE/"restricted_audit_protocol.json")
assert audit["status"]=="PASS_N131_EIGHT_OFFSET_INDEPENDENT_REPLAY"
assert audit["joint_gcd_degrees"]==[0,0,1,0]

n41_factor_ns=(dual["first_block"]["build_and_factor_ns"]+
               dual["second_block"]["build_and_factor_ns"])
n41_join_ns=sum(row["upper_join_ns"] for row in dual["rows"])
n131_families_per_block=1<<28
n131_equal_rate_seconds=(n41_factor_ns/2048)*2*n131_families_per_block/1e9
required_ns_per_family=600e9/(2*n131_families_per_block)
out={"status":"PASS_JOINT_BLOCK_TERMINAL_AUDIT",
    "protocols_checked":list(protocols),
    "n41_dual_factor_ns":n41_factor_ns,
    "n41_four_branch_join_ns":n41_join_ns,
    "n41_dual_root_entries":[dual["first_block"]["root_entries"],
                             dual["second_block"]["root_entries"]],
    "n131_product_families_per_block":n131_families_per_block,
    "n131_two_block_family_total":2*n131_families_per_block,
    "n131_equal_n41_rate_projection_seconds":n131_equal_rate_seconds,
    "n131_required_mean_ns_per_family_for_600_seconds":required_ns_per_family,
    "projection_type":"diagnostic rate transfer only; field arithmetic and source search excluded",
    "candidate_id":None}
with (HERE/"terminal_audit.json").open("x") as output:
    json.dump(out,output,sort_keys=True,indent=2);output.write("\n")
print(out)
