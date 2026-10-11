"""Bind paired 513-point results and summarize the frozen sample."""

import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


p = json.loads((HERE / "protocol.json").read_text())
panel = json.loads((HERE / "panel.json").read_text())
relaxed = json.loads((HERE / "relaxed_receipt.json").read_text())
exact = json.loads((HERE / "exact_receipt.json").read_text())
sage = json.loads((HERE / "sage_replay.json").read_text())
factor = json.loads((HERE / "factorization_gate.json").read_text())
assert p["status"] == "FROZEN_N41_TARGET_DERIVED_RELAXED_EXACT_PANEL"
assert sage["status"] == "PASS_SAGE_REPLAY_ALL_RELAXED_HITS"
assert factor["status"] == "PASS_SEED_CONDITIONED_PRODUCT_IMAGE_GATE"
assert factor["protocol_sha256"] == sha(HERE / "protocol.json")
assert factor["source_sha256"] == sha(HERE / "factorization_gate.py")
assert sage["relaxed_receipt_sha256"] == sha(HERE / "relaxed_receipt.json")
assert sage["exact_receipt_sha256"] == sha(HERE / "exact_receipt.json")
assert p["sha256"]["panel"] == sha(HERE / "panel.json")
assert p["sha256"]["targets"] == sha(HERE / "targets.txt")
assert p["sha256"]["exact_input"] == sha(HERE / "exact_input.txt")
assert p["sha256"]["relaxed_binary"] == sha(HERE / "relaxed_panel_native")
assert p["sha256"]["exact_binary"] == sha(HERE / "exact_panel_native")
assert panel["eligible_count"] == 1711 and panel["selected_count"] == 512
assert len(relaxed["queries"]) == len(exact["queries"]) == 513
assert relaxed["unique_unrotated_curve_points"] == 128656
assert exact["distinct_exact_pair_points"] == [1956, 1956]
relaxed_hits = []
exact_hits = []
for rq, eq in zip(relaxed["queries"], exact["queries"]):
    assert rq["label"] == eq["label"]
    assert rq["target"] == eq["target"]
    assert eq["pair_probes"] == 1956
    if rq["status"] == "RELAXED_SUM_HIT":
        relaxed_hits.append(rq["label"])
        assert rq["probes"] <= 128656
    else:
        assert rq["status"] == "COMPLETE_RELAXED_NO_SUM"
        assert rq["probes"] == 128656
    if eq["status"] == "EXACT_FOUR_ATOM_HIT":
        exact_hits.append(eq["label"])
        assert rq["label"] in relaxed_hits
    else:
        assert eq["status"] == "COMPLETE_EXACT_NO_SUM"
assert relaxed_hits == sage["relaxed_hit_labels"]
assert exact_hits == sage["exact_hit_labels"] == ["positive"]
assert len(relaxed_hits) == 10
assert [row["label"] for row in factor["relaxed_hit_checks"]] == relaxed_hits
assert all(not row["right_factorable"]
           for row in factor["relaxed_hit_checks"][1:])

N, n, k = 1711, 512, 9
denominator = math.comb(N, n)


def cdf_at(x, K):
    return sum(math.comb(K, j)*math.comb(N-K, n-j)
               for j in range(x+1) if j <= K and n-j <= N-K)/denominator


eligible_K = [K for K in range(N+1)
              if cdf_at(k, K) >= 0.025 and 1-cdf_at(k-1, K) >= 0.025]
exact_upper_K = max(K for K in range(N+1)
                    if math.comb(N-K, n)/denominator >= 0.05
                    if N-K >= n)
out = {
    "status": "PASS_PAIRED_N41_TARGET_DERIVED_PANEL_AUDIT",
    "candidate_id": None,
    "eligible_pool": N,
    "sampled_controls": n,
    "relaxed_control_hits": k,
    "exact_control_hits": 0,
    "known_positive_hits_both": True,
    "relaxed_only_labels": [x for x in relaxed_hits if x != "positive"],
    "conditional_uniform_sample_uncertainty": {
        "method": "exact hypergeometric inversion treating seeded shuffle as uniform without replacement",
        "relaxed_population_hit_count_95pct_central": [min(eligible_K), max(eligible_K)],
        "exact_population_hit_count_95pct_one_sided_upper": exact_upper_K,
    },
    "relaxed_reusable_setup_ns": relaxed["reusable_setup_ns"],
    "relaxed_query_sum_ns": sum(row["online_ns"] for row in relaxed["queries"]),
    "exact_reusable_setup_ns": exact["reusable_setup_ns"],
    "exact_query_sum_ns": sum(row["online_ns"] for row in exact["queries"]),
    "relaxed_peak_rss_bytes": relaxed["peak_rss_bytes"],
    "exact_peak_rss_bytes": exact["peak_rss_bytes"],
    "protocol_sha256": sha(HERE / "protocol.json"),
    "panel_sha256": sha(HERE / "panel.json"),
    "relaxed_receipt_sha256": sha(HERE / "relaxed_receipt.json"),
    "exact_receipt_sha256": sha(HERE / "exact_receipt.json"),
    "sage_replay_sha256": sha(HERE / "sage_replay.json"),
    "factorization_gate_sha256": sha(HERE / "factorization_gate.json"),
}
(HERE / "audit.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], "relaxed_only", len(out["relaxed_only_labels"]))
