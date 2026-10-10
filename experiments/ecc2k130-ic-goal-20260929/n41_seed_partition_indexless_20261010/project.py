"""Exact first-bucket W15 loop count for this seed-partition algorithm."""

from collections import Counter
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
SUPPORT=BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv"
SIGNED=BASE/"n131_w15_cross_block_seed_offset_20261010/signed_seed_counts.tsv"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads((HERE/"projection_protocol.json").read_text())
assert freeze["status"]=="FROZEN_BEFORE_W15_FIRST_BUCKET_EXACT_COUNT"
assert freeze["sha256"]=={"project.py":sha(Path(__file__)),
    "native.cpp":sha(HERE/"native.cpp"),
    "support_w15.tsv":sha(SUPPORT),"signed_seed_counts.tsv":sha(SIGNED),
    "protocol.json":sha(HERE/"protocol.json")}
assert not (HERE/"projection.json").exists()
support={int(a):int(b) for a,b in (line.split() for line in SUPPORT.read_text().splitlines())}
signed={int(a):int(b) for a,b in (line.split() for line in SIGNED.read_text().splitlines())}
assert len(support)==16441 and len(signed)==32767
counts={}
for seed in range(1,8):
    pairs=[]
    for a,ca in support.items():
        b=a^seed
        if a<b and b in support and ca!=support[b]:
            pairs.append(tuple(sorted((ca,support[b]))))
    assert signed[seed]==4*len(pairs)
    col=Counter(column for pair in pairs for column in pair)
    joint=Counter(pairs)
    valid=sum(len(pairs)-col[a]-col[b]+joint[(a,b)] for a,b in pairs)
    # Two ordered pair slots, four sign patterns per unordered pair.
    counts[seed]=16*valid
first_bucket=counts[1]*sum(counts.values())
assert first_bucket==519275924305959936
record={"status":"PASS_EXACT_W15_FIRST_BUCKET_LOOP_BOUND",
    "signed_pair_states_by_seed":{str(s):signed[s] for s in counts},
    "distinct_column_four_atom_states_by_seed":{str(s):counts[s] for s in counts},
    "first_bucket_seed_a":1,"first_bucket_allowed_seed_b":list(range(1,8)),
    "first_bucket_cross_iterations_before_column_filter":str(first_bucket),
    "required_iterations_per_second_for_600_seconds":first_bucket/600,
    "count_scope":"native.cpp loops all A seed-one states against B seeds one through seven before free-pair probes; includes states later rejected by cross-block columns",
    "protocol_sha256":sha(HERE/"projection_protocol.json"),
    "candidate_id":None}
with (HERE/"projection.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
print({"status":record["status"],"first_bucket_iterations":first_bucket})
