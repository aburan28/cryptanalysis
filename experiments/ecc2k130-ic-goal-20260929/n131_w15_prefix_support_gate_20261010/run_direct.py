#!/usr/bin/env python3
"""Build and run the independent W15 pair census under its frozen gate."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
W15 = HERE.parent / "n131_w15_coupled_sixpair_20261010"
BINARY = HERE / "audit_seed_counts"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "direct_protocol.json").read_text())
    sources = {"freeze_direct": HERE / "freeze_direct.py",
               "run_direct": Path(__file__),
               "enumerator": HERE / "audit_seed_counts.cpp",
               "w15_support": W15 / "support_w15.tsv",
               "w15_count": W15 / "seed_sum_count.json",
               "support_protocol": W15 / "support_protocol.json"}
    assert protocol["status"] == "FROZEN_BEFORE_DIRECT_W15_PAIR_ENUMERATION"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources.items()}
    compiled = subprocess.run(
        [protocol["compiler"], *protocol["compiler_flags"],
         str(HERE / "audit_seed_counts.cpp"), "-o", str(BINARY)],
        capture_output=True, text=True, timeout=protocol["wall_cap_seconds"])
    assert compiled.returncode == 0, compiled.stderr
    start = time.perf_counter_ns()
    executed = subprocess.run([str(BINARY), str(W15 / "support_w15.tsv")],
                              capture_output=True, text=True,
                              timeout=protocol["wall_cap_seconds"])
    wall_ns = time.perf_counter_ns() - start
    assert executed.returncode == 0, executed.stderr
    values = list(map(int, executed.stdout.split()))
    assert len(values) == 5
    source = json.loads((W15 / "seed_sum_count.json").read_text())
    expected = [int(source[key]) for key in (
        "accepted_unordered_mask_pairs",
        "accepted_signed_pair_states_per_rotation",
        "same_seed_two_pair_states",
        "min_signed_pair_states_per_nonzero_seed",
        "max_signed_pair_states_per_nonzero_seed")]
    assert values == expected, (values, expected)
    receipt = {
        "status": "PASS_DIRECT_W15_SUPPORT_PAIR_ENUMERATION",
        "unordered_mask_pairs": values[0],
        "signed_pair_states_per_rotation": values[1],
        "same_seed_two_pair_states": values[2],
        "minimum_seed_pair_states": values[3],
        "maximum_seed_pair_states": values[4],
        "enumeration_wall_ns_exploratory": wall_ns,
        "source_sha256": {"protocol": sha(HERE / "direct_protocol.json"),
                          "binary": sha(BINARY),
                          **{name: sha(path) for name, path in sources.items()}},
    }
    with (HERE / "direct_result.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(receipt["status"])


if __name__ == "__main__":
    main()
