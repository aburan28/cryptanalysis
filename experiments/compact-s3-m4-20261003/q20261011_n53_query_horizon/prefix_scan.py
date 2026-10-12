#!/usr/bin/env python3
"""Retrospective exact-cost rank scan at every relation-producing prefix."""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import math
import random
import struct
from pathlib import Path
import verify

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "q20261011_n53_native_pair"
ARCHIVE = HERE.parent / "bases/n53_weight3_orbits.json.gz"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    measured = json.loads((HERE / "native_measurement.json").read_text())
    replay = json.loads((HERE / "independent_replay.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    relations = replay["cap_results"]["5000000"]["relations"]
    match_positions = [record["query_number"] for record in relations]
    assert match_positions == [match[0] for match in measured["matches"]]
    assert match_positions == sorted(set(match_positions))
    base = verify.read_points(PRIOR / "inputs/base.bin")
    assert sha(PRIOR / "inputs/base.bin") == freeze["base_input_sha256"]
    onb = verify.field.Onb(53)
    curve = verify.curves.Curve(onb)
    r = protocol["rank_accounting"]["modulus"]
    eigen = protocol["rank_accounting"]["frobenius_eigenvalue_mod_r"]
    with gzip.open(ARCHIVE, "rt") as stream:
        archive = json.load(stream)
    factor = archive["factor_base"]
    packed = base64.b64decode(factor["packed_canonical_x_keys_base64"])
    assert hashlib.sha256(packed).hexdigest() == protocol["factor_base_enumerated_set_sha256"]
    keys = [int.from_bytes(packed[i:i+7], "little") for i in range(0,len(packed),7)]
    point_to_column = {}
    for col,(key,length) in enumerate(zip(keys,factor["orbit_lengths"])):
        representative = curve.pointFromX(onb.fromCoords(key))
        assert representative is not None
        for exponent in range(length):
            positive = curve.frob(representative,exponent)
            negative = curve.neg(positive)
            coeff = pow(eigen,exponent,r)
            assert positive not in point_to_column and negative not in point_to_column
            point_to_column[positive] = col,coeff
            point_to_column[negative] = col,-coeff % r
    assert set(point_to_column) == set(base)
    rows = []
    for record in relations:
        row = [0]*(len(keys)+1)
        for point in record["points"]:
            col,coeff = point_to_column[tuple(point)]
            row[col] = (row[col]+coeff) % r
        row[-1] = r-1
        rows.append(row)
    # Reconstruct the frozen query stream and identity-pair prefix count.
    rng = random.Random(protocol["point_decomposition"]["query_seed"])
    digest = hashlib.sha256()
    target_positions = set(match_positions)
    identity_at = {}
    identities = 0
    for i in range(1,5000001):
        a = rng.randrange(len(base)); b = rng.randrange(len(base))
        digest.update(struct.pack("<HH",a,b))
        x0,y0 = base[a]; x1,y1 = base[b]
        identities += x0 == x1 and (y0 ^ y1) == x0
        if i in target_positions:
            identity_at[i] = identities
    assert digest.hexdigest() == freeze["query_file_sha256"]
    assert identities == measured["query_skipped_identity_pairs"]
    records = []
    prefix_rows = []
    previous_rank = 0
    table = measured["table_states_generated"]
    for position,row in zip(match_positions,rows):
        prefix_rows.append(row)
        rank = verify.rank_mod_r(prefix_rows,r)
        if rank > previous_rank:
            charge = table + 2*position - identity_at[position]
            records.append({"query_position": position,
                            "augmented_rank": rank,
                            "charged_pair_add_attempts": charge,
                            "pair_adds_per_rank_row": charge/rank})
        previous_rank = rank
    assert previous_rank == replay["cap_results"]["5000000"]["augmented_rank"]
    assert len(records) == previous_rank
    best = min(records,key=lambda item:item["pair_adds_per_rank_row"])
    chosen = analysis["best_measured_pair_adds_per_rank_row"]
    output = {"status": "PASS", "proposal_id": "Q1456",
              "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
              "isogeny": "none", "measurement_sha256": sha(HERE / "native_measurement.json"),
              "independent_replay_sha256": sha(HERE / "independent_replay.json"),
              "analysis_sha256": sha(HERE / "analysis.json"),
              "source_sha256": sha(Path(__file__)),
              "selection_status": "retrospective_same_target_diagnostic",
              "rank_increasing_prefixes": records,
              "best_retrospective_prefix": best,
              "improvement_vs_frozen_three_million_cap_ratio": chosen/best["pair_adds_per_rank_row"],
              "improvement_vs_frozen_three_million_cap_bits": math.log2(chosen/best["pair_adds_per_rank_row"]),
              "next_gate": "freeze cap before running an independent ordinary public target"}
    (HERE / "prefix_scan.json").write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print("PASS Q1456 retrospective",best)


if __name__ == "__main__":
    main()
