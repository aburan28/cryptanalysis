#!/usr/bin/env python3
"""Terminal evidence binding for W15 offset support and N41 public row."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    freeze = read("verify_protocol.json")
    assert freeze["status"] == "FROZEN_BEFORE_TERMINAL_AUDIT"
    assert freeze["source_sha256"] == {name: sha(HERE / path)
                                         for name, path in freeze["paths"].items()}
    assert not (HERE / "terminal_audit.json").exists()
    count_protocol = read("protocol.json")
    result = read("result.json")
    direct = read("direct_audit.json")
    query_protocol = read("n41_query_protocol.json")
    query = read("n41_query_receipt.json")
    native = read("n41_native.json")
    hit = read("n41_hit.json")
    sage = read("n41_sage_replay.json")
    assert count_protocol["offsets"] == query_protocol["allowed_offsets"] == list(range(8))
    assert result["status"] == "PASS_EXACT_CROSS_BLOCK_OFFSET_SUPPORT"
    assert direct["status"] == "PASS_DIRECT_W15_OFFSET_COUNT_AUDIT"
    assert result["source_sha256"] == count_protocol["source_sha256"]
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["signed_seed_counts_sha256"] == sha(HERE / "signed_seed_counts.tsv")
    assert result["offset_support_sha256"] == sha(HERE / "offset_support.tsv")
    assert direct["all_32767_seed_counts_match"] and direct["selected_offsets_match"] == 8
    assert direct["direct_counts_sha256"] == sha(HERE / "direct_seed_counts.tsv")
    assert (HERE / "signed_seed_counts.tsv").read_bytes() == (HERE / "direct_seed_counts.tsv").read_bytes()
    offsets = [int(row.split()[1]) for row in (HERE / "offset_support.tsv").read_text().splitlines()]
    assert len(offsets) == 32768
    selected = sum(offsets[:8])
    assert selected == int(result["selected_two_block_states"])
    n = int(result["signed_pair_states_N"])
    r = int(count_protocol["subgroup_order"])
    mean = Fraction(n*n*selected, r)
    assert (str(mean.numerator), str(mean.denominator)) == (
        result["uniform_group_mean_upper"]["numerator"],
        result["uniform_group_mean_upper"]["denominator"])
    assert query["status"] == native["status"] == "FOUND_PENDING_SAGE_REPLAY"
    assert query["process_exit_code"] == 0
    assert query["native"] == native and query["hit"] == hit
    assert query["source_sha256"] == query_protocol["source_sha256"]
    assert query["protocol_sha256"] == sha(HERE / "n41_query_protocol.json")
    assert all(query["artifact_sha256"][name] == sha(HERE / name)
               for name in query["artifact_sha256"])
    assert native["online_ns"] < query_protocol["native_online_cap_seconds"]*10**9
    assert native["peak_rss_bytes"] < query_protocol["rss_cap_bytes"]
    assert native["accepted_probes"] <= query_protocol["max_accepted_probes"]
    assert native["attempts"] >= native["offset_rejects"]+native["accepted_probes"]
    assert hit["seed_sums"][2] == hit["seed_sums"][3]
    assert hit["seed_sums"][4] == hit["seed_sums"][5]
    assert hit["seed_sums"][2]^hit["seed_sums"][4] == 3
    assert sage["status"] == "PASS_N41_PUBLIC_RELATION_AND_OFFSET_IDENTITY_SAGE"
    assert sage["cross_block_offset"] == 3 and sage["distinct_folded_columns"] == 12
    assert sage["public_target"] == hit["raw_sum"] == query_protocol["public_target"]
    assert sage["projected_sum"] == sage["raw_sum_after_cofactor_four"] == hit["raw_sum"]
    assert sage["source_sha256"] == read("n41_sage_protocol.json")["source_sha256"]
    assert sage["protocol_sha256"] == sha(HERE / "n41_sage_protocol.json")
    audit = {"status": "PASS_W15_OFFSET_SUPPORT_AND_N41_PUBLIC_RELATION",
             "candidate_id": None, "curve_id_n131": result["curve_id"],
             "n131_offsets": list(range(8)),
             "n131_uniform_group_mean_upper": result["uniform_group_mean_upper"],
             "n131_one_free_prefix_q50": result[
                 "q50_target_independent_one_free_prefix_union_bound"],
             "n41_public_target": hit["raw_sum"],
             "n41_verified_relation_columns": 12,
             "n41_offset": 3, "n41_online_ns": native["online_ns"],
             "n41_peak_rss_bytes": native["peak_rss_bytes"],
             "source_sha256": freeze["source_sha256"],
             "protocol_sha256": sha(HERE / "verify_protocol.json")}
    with (HERE / "terminal_audit.json").open("x") as stream:
        json.dump(audit, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": audit["status"],
                      "n41_offset": 3, "n131_q50": audit["n131_one_free_prefix_q50"]}))


if __name__ == "__main__":
    main()
