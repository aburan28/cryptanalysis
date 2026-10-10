"""Exact source-pair census and explicitly labeled measured-rate projection."""
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
SUPPORT=BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv"
RESULT=HERE/"as_result.json"


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads((HERE/"projection_protocol.json").read_text())
assert freeze["status"]=="FROZEN_BEFORE_SOURCE_PAIR_CENSUS"
assert freeze["source_sha256"]=={
    "projection.py":digest(Path(__file__)),
    "support_w15.tsv":digest(SUPPORT),
    "as_result.json":digest(RESULT)}
assert not (HERE/"projection_result.json").exists()

source=[tuple(map(int,line.split())) for line in SUPPORT.read_text().splitlines()]
assert len(source)==len({m for m,_ in source})==16441
columns=Counter(column for _,column in source)
all_pairs=len(source)*(len(source)-1)//2
same_column=sum(count*(count-1)//2 for count in columns.values())
valid_pairs=all_pairs-same_column
assert valid_pairs>0
measured=json.loads(RESULT.read_text())
assert measured["status"]=="PASS_N131_W15_ONE_SIDED_AS_JOIN_CONTROLS"
one_seed=measured["usable_product_pairs"]
positive_ns=measured["positive"]["elapsed_ns"]
projected_ns=positive_ns*valid_pairs//one_seed
record={"status":"PASS_EXACT_SOURCE_PAIR_CENSUS_WITH_EXPLORATORY_RATE_PROJECTION",
        "field_degree":131,"source_dimension":15,
        "actual_supported_source_masks":len(source),
        "distinct_support_columns":len(columns),
        "all_unordered_supported_pairs":all_pairs,
        "same_column_unordered_pairs":same_column,
        "different_column_unordered_pairs":valid_pairs,
        "nonzero_seed_sums":(1<<15)-1,
        "measured_seed":measured["seed"],
        "measured_usable_pairs":one_seed,
        "measured_one_residual_join_ns":positive_ns,
        "linear_rate_projection_one_residual_all_seeds_s":projected_ns/1e9,
        "projection_scope":"Assumes fixed four-pair prefix and same per-pair rate for every nonzero seed; excludes all other target-dependent stages; unisolated host; not a bound or verified query.",
        "source_sha256":freeze["source_sha256"],
        "protocol_sha256":digest(HERE/"projection_protocol.json")}
with (HERE/"projection_result.json").open("x") as stream:
    json.dump(record,stream,sort_keys=True,indent=2)
    stream.write("\n")
print({"status":record["status"],"pairs":valid_pairs,
       "projected_s":record["linear_rate_projection_one_residual_all_seeds_s"]})
