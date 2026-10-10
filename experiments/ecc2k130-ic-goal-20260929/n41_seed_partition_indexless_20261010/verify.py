"""Terminal source, native run, Sage replay, and W15 bound audit."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
INPUT=BASE/"n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"
HELPER=BASE/"n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
SCREEN=BASE/"n41_n131_diagonal_atom_20261010/screen.json"
SUPPORT=BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv"
SIGNED=BASE/"n131_w15_cross_block_seed_offset_20261010/signed_seed_counts.tsv"


def read(path):return json.loads(path.read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


protocol=read(HERE/"protocol.json")
assert protocol["status"]=="FROZEN_BEFORE_N41_SEED_PARTITION_PUBLIC_QUERY"
native_sources={"native.cpp":HERE/"native.cpp","native":HERE/"native",
    "run.py":HERE/"run.py","input":INPUT,"helper.cpp":HELPER,
    "sage_runtime_info":HERE/"sage_runtime_info.json"}
assert protocol["sha256"]=={name:sha(path) for name,path in native_sources.items()}
receipt=read(HERE/"receipt.json")
native=read(HERE/"native_result.json")
hit=read(HERE/"hit.json")
assert receipt["status"]==native["status"]=="FOUND_PENDING_SAGE_REPLAY"
assert receipt["process_exit_code"]==0 and receipt["protocol_sha256"]==sha(HERE/"protocol.json")
assert receipt["source_sha256"]==protocol["sha256"]
assert receipt["artifact_sha256"]=={name:sha(HERE/name) for name in
    ("hit.json","native_result.json","stdout.txt","stderr.txt")}
assert native["free_four_index_entries"]==0 and native["found_seed"]==1
assert native["online_ns"]<120*10**9 and native["peak_rss_bytes"]<4294967296
assert native["right_tested"]==5332992 and native["right_inserted"]==2643968
assert native["free_tested"]==395533
assert hit["raw_sum"]==protocol["public_target"]
assert len(set(hit["columns"]))==12

replay_protocol=read(HERE/"replay_protocol.json")
replay_sources={"audit":HERE/"replay.py","screen":SCREEN,"input":INPUT,
    "native":HERE/"native_result.json","hit":HERE/"hit.json",
    "query_receipt":HERE/"receipt.json","runtime":HERE/"sage_runtime_info.json"}
assert replay_protocol["source_sha256"]=={name:sha(path) for name,path in replay_sources.items()}
replay=read(HERE/"replay_result.json")
assert replay["status"]=="PASS_N41_SEED_PARTITION_PUBLIC_RELATION_SAGE"
assert replay["protocol_sha256"]==sha(HERE/"replay_protocol.json")
assert replay["source_sha256"]==replay_protocol["source_sha256"]
assert replay["distinct_folded_columns"]==12 and replay["summands"]==12
assert replay["public_target"]==protocol["public_target"]
assert replay["projected_sum"]==protocol["public_target"]
assert replay["raw_sum_after_cofactor_four"]==protocol["public_target"]
assert replay["cross_block_offset"]==3

projection_protocol=read(HERE/"projection_protocol.json")
projection_sources={"project.py":HERE/"project.py","native.cpp":HERE/"native.cpp",
    "support_w15.tsv":SUPPORT,"signed_seed_counts.tsv":SIGNED,
    "protocol.json":HERE/"protocol.json"}
assert projection_protocol["sha256"]=={name:sha(path) for name,path in projection_sources.items()}
projection=read(HERE/"projection.json")
assert projection["status"]=="PASS_EXACT_W15_FIRST_BUCKET_LOOP_BOUND"
assert projection["protocol_sha256"]==sha(HERE/"projection_protocol.json")
assert int(projection["first_bucket_cross_iterations_before_column_filter"])==519275924305959936

out={"status":"PASS_N41_SEED_PARTITION_TERMINAL_AUDIT",
    "candidate_id":None,"curve_id":protocol["curve_id"],
    "public_target":protocol["public_target"],
    "verified_columns":replay["distinct_folded_columns"],
    "online_ns":native["online_ns"],
    "peak_rss_bytes":native["peak_rss_bytes"],
    "first_bucket_w15_iterations":projection["first_bucket_cross_iterations_before_column_filter"],
    "protocol_sha256":sha(HERE/"protocol.json"),
    "replay_protocol_sha256":sha(HERE/"replay_protocol.json"),
    "projection_protocol_sha256":sha(HERE/"projection_protocol.json")}
with (HERE/"terminal_audit.json").open("x") as output:
    json.dump(out,output,sort_keys=True,indent=2);output.write("\n")
print(out)
