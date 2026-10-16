#!/usr/bin/env python3
"""Write the frozen protocol (`protocol.json`) of the n=83 stacked experiment.

Run once, before any timing, after `make_power_prior.py`, `power_check.py`,
`make_targets.py` and `make_online_source.py`; `restore.py` re-checks every
digest it records. Adapted from `koblitz-n83-state-fold-20261015`'s
`make_protocol.py`.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_TABLE = "../koblitz-single-target-n83-tier1-20261014/tier1_github_38523707244/precompute/factor_logs_n83_K600.json"
BINARY = "ic_online_stacked_r770"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import restore  # noqa: E402  (this directory)

    power = json.loads((HERE / "analysis" / "power.json").read_text())
    targets = json.loads((HERE / "inputs" / "cold_targets.json").read_text())
    q0 = json.loads((HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json")
                    .read_text())["q0"]["point"]
    archived_q0 = json.loads((HERE / "inputs" / "archived_identities.json").read_text())["old17"]["q0"]
    points = len(targets["points"])
    cold = lambda **kw: dict({"kind": "ic_cold", "binary": BINARY}, **kw)  # noqa: E731
    rank = lambda **kw: dict({"kind": "ic_rank", "binary": BINARY}, **kw)  # noqa: E731
    stack_rank = {"rank_canon": "lift", "rank_order": "feistel", "rank_probe": "target"}
    arms = {
        "cP": cold(table="base", fold=False,
                   role=("baseline: the probe-pipeline producer pP (lift_scan x Feistel + prefetched probes, "
                         "32-byte root table, unfolded index; koblitz-n83-probepipe-20261015, promoted by run "
                         "38822490448), cold with the verified cached factor-log table")),
        "cS": cold(table="compact", fold=True,
                   role=("candidate: the stack, pP + 16-byte compact slots (koblitz-n83-tablefilter-20261015) + "
                         "folded S3 root index (koblitz-n83-state-fold-20261015), cold with the cached table")),
        "cSaa": cold(table="compact", fold=True, role="A/A control: a second process of cS"),
        "cSX": cold(table="compact", fold=True, plant=True,
                    role=("planted positive control: cS plus the work the fold removes, redone and discarded "
                          "(every mate's S3 solve and two canonicalizations in the build; every skipped state "
                          "rescanned online into fold_audit_probes)")),
        "cSmF": cold(table="compact", fold=False, role="ablation: the stack minus the fold (compact slots, unfolded)"),
        "cSmS": cold(table="base", fold=True,
                     role="ablation: the stack minus the compact slots (32-byte table, folded)"),
        "cSF": cold(table="filter", fold=True,
                    role="secondary (optional component): the stack plus the 32 MiB root filter (KIC_ROOT_TABLE=filter)"),
        "cSI": cold(table="compact", fold=True, index_canon="lift",
                    role="secondary (optional component): the stack with lift_scan canonicalizing the index build"),
        "rT": {"kind": "rho_tuned", "binary": "rho_tuned_r770",
               "role": "A's tuned rho rT770 (Fold/64/DP6), the strongest one-target rho at n=83, same points"},
        "kP": rank(table="base", fold=False, rank_canon="full", rank_order="left_major", rank_probe="off",
                   role=("pP's rank stage as B runs it (32-byte table, unfolded, full scan, left-major, sequential "
                         "probes), then one target with pP's online path")),
        "kS": rank(table="compact", fold=True, **stack_rank,
                   role=("the stack's rank stage: lift_scan, Feistel order, the stack's own probe loop on the "
                         "16-byte table over the folded index, then one target")),
        "kSaa": rank(table="compact", fold=True, **stack_rank, role="A/A control: a second process of kS"),
        "kSmF": rank(table="compact", fold=False, **stack_rank, role="ablation: kS minus the fold"),
        "kSmS": rank(table="base", fold=True, **stack_rank,
                     role="ablation: kS minus the compact slots (prefetch pipeline on the 32-byte table)"),
    }
    cold_arms = ["cP", "cS", "cSaa", "cSX", "cSmF", "cSmS", "cSF", "cSI", "rT"]
    rank_arms = ["kP", "kS", "kSaa", "kSmF", "kSmS"]
    order = (["O1"] + ["C%d" % i for i in range(1, 5)] + ["K1"] + ["C%d" % i for i in range(5, 13)] + ["K2"] +
             ["C%d" % i for i in range(13, points + 1)])
    protocol = {
        "schema": 1,
        "kind": "n83-stacked-e2e-cold-tier1",
        "frozen_before_any_timing": True,
        "frozen_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "question": ("Does the stacked n=83 K600 one-target IC producer (lift_scan x Feistel + prefetched probes "
                     "+ 16-byte compact root slots + folded S3 root index, with its rank stage on the same "
                     "probe loop) lower the END-TO-END cold cost (setup + index build + rank stage + linear "
                     "algebra + one-target online) of the current best, the probe-pipeline producer pP with its "
                     "rank stage as B runs it, on new targets, with every relation, scalar and the factor-log "
                     "table unchanged?"),
        "success_criterion": "AGENTS.md 'Success criterion: iterative improvement of the index-calculus baseline'",
        "current_baseline": ("the probe-pipeline producer pP (koblitz-n83-probepipe-20261015, run 38822490448), "
                             "the last promoted producer whose rank stage is B's; the compact slots "
                             "(run 38829449594) and the fold (run 38819494806) were each promoted on their own "
                             "parent, never stacked or measured end to end"),
        "sources": {
            "crypto_770f6a69": "770f6a6925a0d29b768bd79074f54a173e967fe7 (snapshots/r770 via ../koblitz-n83-reconcile-20261014/restore_sources.py)",
            "tablefilter_producer": ("koblitz-n83-tablefilter-20261015 make_online_source.py (make_tablefilter_source.py "
                                     "here, verbatim with its two parents), output sha256 "
                                     "70233510e07a9e1858793502ed85080711cd3d8a1b0fa3357861fe20a32dba0c"),
            "fold_port": "koblitz-n83-state-fold-20261015 make_online_source.py FOLD_CODE and fold_edits, ported in make_online_source.py",
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
            "root_table_slots": {"unfolded": 1 << 27, "folded": 1 << 26},
            "root_filter_log2_bits": 28,
            "index_digest": {"logical_states": 29880000,
                             "logical_states_blake3": "baf46d5a34732aa2aeba1fc0ca4f57036e3c324ade0bf8791431c838fe15d7ec",
                             "table_entries": 29878182, "table_map_sum64": "be14a80705232396",
                             "table_map_xor64": "8132bdcfd619010f",
                             "source": ("B's unfolded index, protocol.json of koblitz-n83-state-fold-20261015; "
                                        "reproduced here by cP and cS on Q0 (smoke/)")},
            "factor_log_table": LOG_TABLE,
            "factor_log_table_sha256": sha256(HERE / LOG_TABLE),
            "tuned_rho_config": "snapshots/r770/research/n83_evaluation_20261012/optimization/selected_config.json",
            "cold_targets_file": ("inputs/cold_targets.json (role stacked-cold-v1; disjoint from Q0, B's panel and "
                                  "every earlier n=83 panel of the law on main)"),
            "q0_identity": {"relation": archived_q0["feistel"]["relation"], "scalar": archived_q0["scalar"],
                            "probes_unfolded": archived_q0["feistel"]["probes"], "probes_folded": 1987852,
                            "source": ("inputs/archived_identities.json old17.q0 (run 38786433493); folded probes "
                                       "from koblitz-n83-state-fold-20261015 (Q0 smoke, cF) and smoke/ here")},
            "cold_interval": ("producer's own clock: process start (main) .. recovery_check_end of the one target = "
                              "setup_complete + the five online phases (cold_in_process_ms); in ic_cold the rank "
                              "stage is skipped (verified cached table); the index digest runs after the target, "
                              "outside every interval"),
            "rank_interval": ("timing_ms.rank_stage of an ic_rank process: the guided rank stage to full rank (query, "
                              "PDP, relation check per attempt, echelon insert); its process's cold_in_process_ms "
                              "also includes setup, linear algebra and one target"),
            "online_interval": "target_query_begin .. recovery_check_end, five exclusive phases (unchanged)",
        },
        "arms": arms,
        "design": {
            "cold_points": points,
            "power_chosen_size": power["chosen_panel_size"],
            "cold_arms": cold_arms,
            "rank_arms": rank_arms,
            "q0_arms": ["cP", "cS"],
            "q0_point": [str(v) for v in q0],
            "rho_seed_base": 870000,
            "rank_blocks": [{"id": "K1", "unit": "s000", "rank_seed": 101}, {"id": "K2", "unit": "s001", "rank_seed": 102}],
            "segment_order": order,
            "within_segment_order": ("random.Random(2026101600 + block).shuffle (C), random.Random(2026101700 + block) (K), "
                                     "random.Random(2026101800) (O)"),
            "process_model": "one point per process, fresh process per run, one pinned CPU, one runner",
            "segment_upper_estimate_s": {"C": 480, "K": 2700, "O": 300},
            "timeout_s": {"ic_cold": 600, "ic_rank": 2700, "rho_tuned": 600},
            "time_guard": "skip a segment (rows skipped_time_guard) if elapsed + its estimate exceeds 300 min",
            "runtime_estimate": ("from run 38819494806 (state fold) and run 38829449594 (table filter): build about 10-15 "
                                 "min; cold segment about 270 s (cP 45-52 s, cSmF 45-50, cSX 40, cS, cSaa, cSmS, cSF "
                                 "22-26 each, cSI 17-20, rT 3); rank block about 1,900 s (kP 800-900, kS, kSaa, kSmF, "
                                 "kSmS 220-300 each); total about 3 h, up to about 3.5 h on a slower runner"),
        },
        "gates": [
            "every scheduled row valid (exit 0, verified, schedule match, no memory event)",
            ("every IC process: lift_scan, Feistel, prefetch; the arm's root-table layout with 2^27 slots unfolded and "
             "2^26 folded; logical state count 29,880,000; stored 14,940,300 iff folded; 29,878,182 table entries; "
             "logical-state blake3 and table-map digests equal B's (online.index_digest); no root bloom; no "
             "filter-rejected key found"),
            "per point: one scalar across every IC process (cold and rank) and rT, replayed as [d]G = Q in the pinned oracle",
            "per point: one relation (point indices) across every IC process on the point",
            ("per point: probes cP = cSmF (= kP, kSmF targets); probes cS = cSaa = cSX = cSmS = cSF = cSI (= kS, kSaa, "
             "kSmS targets) <= cP; probes cSX + fold_audit_probes(cSX) = cP"),
            "Q0 (O1): cP and cS give the archived Feistel relation and scalar; probes 1,988,184 (cP) and 1,987,852 (cS)",
            ("rank arms: full rank and the written factor-log table equal to B's archived table, log for log; per block, "
             "rank_relations_blake3 identical across kS, kSaa, kSmF, kSmS; per-attempt probes identical across kS, "
             "kSaa, kSmS and kSmF >= kS attempt by attempt"),
        ],
        "controls_pass_rule": {
            "aa": "E2E(kS + cS) / E2E(kSaa + cSaa) and cold cS / cSaa point estimates both inside [0.97, 1.03]",
            "planted": "cSX / cS ratio of mean cold totals, 95% bootstrap lower bound above 1",
            "otherwise": "verdict invalid",
        },
        "statistics": {
            "end_to_end_cold": ("E2E(k, c) = mean over k's rank processes of timing_ms.rank_stage + mean over the cold "
                                "points of cold_in_process_ms(c); the cold processes hold setup + online, the rank "
                                "processes the rank stage, so E2E = setup + index build + rank stage + linear "
                                "algebra + one-target online"),
            "primary": ("R = E2E(kP, cP) / E2E(kS, cS), bootstrap: the cold points resampled (paired across arms) and, "
                        "independently for each rank process, its attempts resampled (its non-attempt time kept), "
                        "10,000 draws, seed 20261016"),
            "primary_is": "the END-TO-END cold ratio; the online ratio is co-reported as a secondary and never decides",
            "secondary": [
                "online cP/cS (ratio of means and geometric means), cold without the rank stage, setup, index-build and peak-RSS ratios cP/cS",
                "ablations: E2E(kSmF, cSmF)/E2E(kS, cS) and E2E(kSmS, cSmS)/E2E(kS, cS); online, cold-without-rank and setup cSmF/cS and cSmS/cS (the fold's online cost is cSmF/cS online < 1)",
                "optional components: cS/cSF and cS/cSI (cold without rank, online, setup)",
                "rank stage: kP/kS, kSmF/kS, kSmS/kS, kS/kSaa stage ratios and per-attempt cost ratios (bootstrap over attempts); each rank process's single-process end-to-end cold time",
                "rho ms/step from rT; S = cost / (rho ms/step) / sqrt(r) for E2E cold, cold without rank and online, per arm; delta S cP to cS; E2E cold gap IC / rT (cold) and online gaps to rT",
            ],
        },
        "decision_rule": {
            "improvement": "R lower bound > 1 (the stack becomes the new n=83 end-to-end cold baseline)",
            "regression": "R upper bound < 1",
            "not_separated": "otherwise",
            "invalid": "any gate or control fails, or any scheduled row is missing (including time-guard skips)",
        },
        "multiplicity": "one primary statistic; every secondary is descriptive and never changes the verdict",
        "power": {"file": "analysis/power.json", "chosen": power["chosen_panel_size"], "frozen_size": points,
                  "min_delta": power["min_delta"], "expected_ratio_under_prior": power["expected_e2e_ratio_under_prior"]},
    }
    (HERE / "protocol.json").write_text(json.dumps(protocol, indent=1, sort_keys=True) + "\n")
    print(str(HERE / "protocol.json"))


if __name__ == "__main__":
    main()
