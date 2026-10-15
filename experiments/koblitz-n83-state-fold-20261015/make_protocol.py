#!/usr/bin/env python3
"""Write the frozen protocol (`protocol.json`) of the n=83 state-fold experiment.

Run once, before any timing, after `power_check.py`, `make_targets.py` and
`make_online_source.py`; `restore.py` re-checks every digest it records.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import restore  # noqa: E402  (this directory)

    power = json.loads((HERE / "analysis" / "power.json").read_text())
    targets = json.loads((HERE / "inputs" / "cold_targets.json").read_text())
    points = len(targets["points"])
    feistel_lf = {"canon": "lift", "order": "feistel"}
    cold = lambda **kw: dict({"kind": "ic_cold", "binary": "ic_online_statefold_r770"}, **kw)  # noqa: E731
    arms = {
        "cB": cold(fold=False, **feistel_lf,
                   role="baseline: the combined producer (lift_scan x Feistel, claude/n83-combined), unfolded index"),
        "cF": cold(fold=True, **feistel_lf, role="candidate: the same producer on the folded index"),
        "cFaa": cold(fold=True, **feistel_lf, role="A/A control: a second process of cF"),
        "cX": cold(fold=True, plant=True, **feistel_lf,
                   role=("planted positive control: cF plus the work the fold removes, redone and discarded "
                         "(every mate's S3 solve and two canonicalizations in the build; every skipped "
                         "state rescanned online into fold_audit_probes)")),
        "cBL": cold(fold=False, canon="lift", order="left_major", role="secondary: lift_scan-only single arm, unfolded"),
        "cFL": cold(fold=True, canon="lift", order="left_major", role="secondary: lift_scan-only single arm, folded"),
        "cBF": cold(fold=False, canon="full", order="feistel", role="secondary: Feistel-only single arm, unfolded"),
        "cFF": cold(fold=True, canon="full", order="feistel", role="secondary: Feistel-only single arm, folded"),
        "cFI": cold(fold=True, index_canon="lift", **feistel_lf,
                    role="secondary (next improvement): cF with lift_scan canonicalizing the index build"),
        "rT": {"kind": "rho_tuned", "binary": "rho_tuned_r770",
               "role": "A's tuned rho rT770 (Fold/64/DP6), the strongest one-target rho at n=83, same points"},
        "kB": {"kind": "ic_rank", "binary": "ic_online_statefold_r770", "fold": False,
               "rank_canon": "full", "rank_order": "left_major", **feistel_lf,
               "role": "rank stage as B runs it (unfolded, full scan, left-major), then one target"},
        "kN": {"kind": "ic_rank", "binary": "ic_online_statefold_r770", "fold": True,
               "rank_canon": "lift", "rank_order": "feistel", **feistel_lf,
               "role": "rank stage on the folded index with lift_scan and the Feistel order, then one target"},
    }
    cold_arms = ["cB", "cF", "cFaa", "cX", "cBL", "cFL", "cBF", "cFF", "cFI", "rT"]
    order = (["C%d" % i for i in range(1, 5)] + ["K1"] + ["C%d" % i for i in range(5, 11)] + ["K2"] +
             ["C%d" % i for i in range(11, points + 1)])
    protocol = {
        "schema": 1,
        "kind": "n83-state-fold-cold-tier1",
        "frozen_before_any_timing": True,
        "frozen_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "question": ("Does folding the duplicate ordered states (l, r, rel) ~ (r, l, -rel) of the n=83 K600 "
                     "S3 root index lower the cold cost (setup + one-target online) of the combined "
                     "one-target IC, with the same relation, scalar and table, on new targets?"),
        "success_criterion": "AGENTS.md 'Success criterion: iterative improvement of the index-calculus baseline'",
        "current_baseline": ("the combined producer (claude/n83-combined @ 88e1929fb, lift_scan x Feistel; its run "
                             "38803625711 had no result when this froze). If that run does not promote the "
                             "combination, the better single arm is the baseline: cBL/cFL and cBF/cFF answer it."),
        "sources": {
            "crypto_770f6a69": "770f6a6925a0d29b768bd79074f54a173e967fe7 (snapshots/r770 via ../koblitz-n83-reconcile-20261014/restore_sources.py)",
            "combined_producer": "claude/n83-combined @ 88e1929fb make_online_source.py (combined_derivation.py here), output sha256 f65e518a1644962f7b20dcc718d47a0620b43871cd083523e6f827a6d9f56a7e",
            "online_source_sha256": sha256(restore.DERIVED),
            "local_sha256": {key: sha256(path) for key, path in restore.local_files().items()},
        },
        "online": {
            "base": "snapshots/r770/experiments/koblitz-single-target-n83-20261006/base_n83_K600.jsonl",
            "base_hash": "d4a4da26d6e7cb09367de922d9806631fe49989f70d378cae76f347f8d76a9f7",
            "curve_id": "EC1N83Ce1h35c7ced6b497",
            "subgroup_order": "8569786107849059",
            "sqrt_r": 92573139.235,
            "orbit_columns": 600,
            "regular_states": 29880000,
            "stored_states_folded": 14940300,
            "root_table_entries": 29878182,
            "index_digest": {"logical_states": 29880000,
                             "logical_states_blake3": "baf46d5a34732aa2aeba1fc0ca4f57036e3c324ade0bf8791431c838fe15d7ec",
                             "table_entries": 29878182, "table_map_sum64": "be14a80705232396",
                             "table_map_xor64": "8132bdcfd619010f",
                             "source": "B's unfolded index (cB configuration), local smoke on the cloud-agent VM; deterministic"},
            "factor_log_table": "../koblitz-single-target-n83-tier1-20261014/tier1_github_38523707244/precompute/factor_logs_n83_K600.json",
            "factor_log_table_sha256": sha256(HERE.parent / "koblitz-single-target-n83-tier1-20261014/tier1_github_38523707244/precompute/factor_logs_n83_K600.json"),
            "tuned_rho_config": "snapshots/r770/research/n83_evaluation_20261012/optimization/selected_config.json",
            "cold_targets_file": "inputs/cold_targets.json (role statefold-cold-v1; disjoint from Q0, panel B, scanorder-heldout and combined-primary-v1)",
            "cold_interval": ("producer's own clock: process start (main) .. recovery_check_end of the one target = "
                              "setup_complete + the five online phases (cold_in_process_ms); the rank stage is "
                              "skipped (verified cached table) and measured separately by kB/kN; the index digest "
                              "runs after the target, outside every interval"),
            "online_interval": "target_query_begin .. recovery_check_end, five exclusive phases (unchanged)",
        },
        "arms": arms,
        "design": {
            "cold_points": points,
            "power_chosen_size": power["chosen_panel_size"],
            "cold_arms": cold_arms,
            "rho_seed_base": 850000,
            "rank_blocks": [{"id": "K1", "unit": "s000", "rank_seed": 101}, {"id": "K2", "unit": "s001", "rank_seed": 102}],
            "segment_order": order,
            "within_segment_order": "random.Random(2026101600 + block).shuffle (C), random.Random(2026101700 + block) (K)",
            "process_model": "one point per process, fresh process per run, one pinned CPU, one runner",
            "segment_upper_estimate_s": {"C": 600, "K": 2400},
            "timeout_s": {"ic_cold": 600, "ic_rank": 2700, "rho_tuned": 600},
            "time_guard": "skip a segment (rows skipped_time_guard) if elapsed + its estimate exceeds 325 min",
        },
        "gates": [
            "every scheduled row valid (exit 0, verified, schedule match, no memory event)",
            "every IC process: logical state count 29,880,000; stored 14,940,300 iff folded; root table entries, logical-state blake3 and table-map digests equal B's (online.index_digest)",
            "per point: one scalar across every IC arm and rT, replayed as [d]G = Q in the pinned oracle",
            "per point: one relation (point indices) across cB, cF, cFaa, cX, cBF, cFF, cFI (Feistel order), and one across cBL, cFL (left-major)",
            "per point: probes cB = cBF; probes cF = cFaa = cX = cFF = cFI <= cB; probes cX + fold_audit_probes(cX) = cB; probes cFL <= cBL",
            "rank arms: full rank and the written factor-log table equal to B's archived table, log for log",
        ],
        "controls_pass_rule": {
            "aa": "cF / cFaa ratio of mean cold totals inside [0.97, 1.03]",
            "planted": "cX / cF ratio of mean cold totals, 95% bootstrap lower bound above 1",
            "otherwise": "verdict invalid",
        },
        "statistics": {
            "primary": "R = mean cold(cB) / mean cold(cF) over the cold points, bootstrap over points (10,000 resamples, seed 20261015)",
            "secondary": [
                "setup, online, index-build and peak-RSS ratios cB/cF (ratio of means; online also geometric means)",
                "single arms: cBL/cFL and cBF/cFF cold ratios; better unfolded single arm / cF",
                "cF/cFI (lift_scan in the index build)",
                "rank stage: kB/kN total ms per block and the per-attempt mean cost ratio (bootstrap over attempts)",
                "rho ms/step from rT; cold S (setup + online) and ledger cold S (rank + setup + online) for old and new, with deltas; cold and online gaps to rT",
            ],
        },
        "decision_rule": {
            "improvement": "R lower bound > 1 (the fold becomes the new n=83 cold baseline)",
            "regression": "R upper bound < 1",
            "not_separated": "otherwise",
            "invalid": "any gate or control fails",
        },
        "multiplicity": "one primary statistic; every secondary is descriptive and never changes the verdict",
        "power": {"file": "analysis/power.json", "chosen": power["chosen_panel_size"], "frozen_size": points,
                  "min_delta": power["min_delta"]},
    }
    (HERE / "protocol.json").write_text(json.dumps(protocol, indent=1, sort_keys=True) + "\n")
    print(str(HERE / "protocol.json"))


if __name__ == "__main__":
    main()
