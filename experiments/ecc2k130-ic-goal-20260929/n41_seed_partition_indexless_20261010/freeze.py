"""Freeze source, binary, public input, and resource policy before query."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
INPUT=BASE/"n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"
HELPER=BASE/"n131_w18_four_pairs/native_join/frozen_source/helper.cpp"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


sources={"native.cpp":HERE/"native.cpp","native":HERE/"native",
         "run.py":HERE/"run.py","input":INPUT,"helper.cpp":HELPER,
         "sage_runtime_info":HERE/"sage_runtime_info.json"}
assert all(path.exists() for path in sources.values())
assert list(map(int,INPUT.read_text().splitlines()[0].split()))==[
    1458168294740,1672312028033,549756390943,6]
record={"status":"FROZEN_BEFORE_N41_SEED_PARTITION_PUBLIC_QUERY",
        "curve_id":"EC1N41Ckb1h023d9a38bbf7",
        "public_target":[1458168294740,1672312028033],
        "subgroup_order":"549756390943",
        "input_law":"unfixed six W6 signed pairs, two within-block equal seed sums, eight cross-block seed offsets, increasing seed partition order",
        "seed_order":list(range(1,64)),"allowed_offsets":list(range(8)),
        "native_online_cap_seconds":120,"parent_cap_seconds":130,
        "rss_cap_bytes":4294967296,"workers":1,"candidate_id":None,
        "sha256":{name:sha(path) for name,path in sources.items()},
        "compiler":subprocess.check_output(["clang++","--version"],text=True).splitlines()[0],
        "build_command":"clang++ -std=c++17 -O3 -o native native.cpp"}
with (HERE/"protocol.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
