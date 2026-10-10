#!/usr/bin/env python3
"""Freeze a second A1 relation-query stream before inspecting collector outputs."""

import hashlib
import json
import platform
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORDER = 21_044_858_204_113
COUNT = 2_048
SEED = 20261109


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    primary = json.loads((HERE / "inputs/primary.json").read_text())
    prior = {q["known_scalar"] for q in primary["queries"]}
    assert len(prior) == COUNT
    rng = random.Random(SEED)
    queries = [{"source_batch": "allhit_bloom_disjoint",
                "source_query_index": i + 1,
                "known_scalar": rng.randrange(1, ORDER),
                "base_start": rng.randrange(12_720)} for i in range(COUNT)]
    scalars = {q["known_scalar"] for q in queries}
    assert len(scalars) == COUNT and not (scalars & prior)
    identity = dict(primary["identity"])
    identity.update({"query_law": "Python Random seed 20261109; uniform nonzero known scalar then uniform base rotation",
                     "random_seed": SEED,
                     "python_version": platform.python_version(),
                     "queries": queries})
    stream_id = hashlib.sha256(canonical({"curve_id": identity["curve_id"],
        "subgroup_order": ORDER, "generator": identity["generator"],
        "query_law": identity["query_law"], "queries": queries})).hexdigest()[:12]
    workload_id = hashlib.sha256(canonical(identity)).hexdigest()[:12]
    workload = dict(primary)
    workload.update({"identity": identity, "queries": queries,
                     "query_stream_id": stream_id, "workload_id": workload_id,
                     "stream_sha256": None,
                     "base_export_sha256": digest(HERE / "inputs/export.json"),
                     "index_binary_sha256": digest(HERE / "inputs/index.bin")})
    path = HERE / "inputs/disjoint.json"
    with path.open("x") as output:
        json.dump(workload, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps({"status": "frozen", "workload_id": workload_id,
                      "query_stream_id": stream_id, "scalar_overlap": 0}))


if __name__ == "__main__":
    main()
