#!/usr/bin/env python3
"""Write the frozen protocol (`protocol.json`) of the n=83 rank-cut experiment.

Run once, before any timing, after `make_power_prior.py`, `power_check.py`,
`make_targets.py` and `make_online_source.py`; `restore.py` re-checks every
digest it records. `koblitz-n83-stacked-20261016`'s `make_protocol.py`
with this experiment's arms, blocks, gates and paired bootstrap.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_TABLE = "../koblitz-single-target-n83-tier1-20261014/tier1_github_38523707244/precompute/factor_logs_n83_K600.json"
BINARY = "ic_online_rankcut_r770"
STACKED = HERE.parent / "koblitz-n83-stacked-20261016"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import restore  # noqa: E402  (this directory)

    power = json.loads((HERE / "analysis" / "power.json").read_text())
    targets = json.loads((HERE / "inputs" / "cold_targets.json").read_text())
    stacked = json.loads((STACKED / "protocol.json").read_text())
    q0 = stacked["design"]["q0_point"]
    points = len(targets["points"])
    blocks = power["chosen_rank_blocks"]
    if blocks is None:
        raise SystemExit("the power check found no passing block count")
    cold = lambda **kw: dict({"kind": "ic_cold", "binary": BINARY, "table": "compact", "fold": True}, **kw)  # noqa: E731
    rank = lambda **kw: dict({"kind": "ic_rank", "binary": BINARY, "table": "compact", "fold": True,  # noqa: E731
                              "rank_canon": "lift", "rank_order": "feistel", "rank_probe": "target"}, **kw)
    arms = {
        "cS": cold(role=("baseline cold: the stacked producer (koblitz-n83-stacked-20261016 arm cS, the n=83 "
                         "baseline of docs/ic/BASELINES.md), setup + one-target online with the verified "
                         "cached factor-log table")),
        "cR": cold(role=("candidate cold: the rank-cut producer's cold path, which is the stacked producer's code "
                         "(KIC_RANK_SOLVE is read only by the rank stage, which a cold process skips); its own "
                         "processes, so the candidate's end-to-end cost is measured on its own rows")),
        "cRI": cold(index_canon="lift",
                    role=("secondary (optional component): cR with lift_scan canonicalizing the index build "
                          "(KIC_INDEX_CANON=lift; the stacked run's cSI, 1.33x cold without rank)")),
        "rT": {"kind": "rho_tuned", "binary": "rho_tuned_r770",
               "role": "A's tuned rho rT770 (Fold/64/DP6), the strongest one-target rho at n=83, same points"},
        "kS": rank(rank_solve="s3",
                   role=("baseline rank stage: the stack's (lift_scan, Feistel, the 16-byte compact loop over the "
                         "folded index, partner roots by the batched S3 root solve), then one target")),
        "kR": rank(rank_solve="padd",
                   role=("candidate rank stage: kS with the partner roots by point addition from each stored "
                         "root's y (KIC_RANK_SOLVE=padd), exact S3 order resolved at every hit, then one target")),
        "kRaa": rank(rank_solve="padd", role="A/A control: a second process of kR"),
        "kRX": rank(rank_solve="padd_plant",
                    role=("planted positive control: kR plus the work it removes (the S3 batch solve and both "
                          "partners' normal-basis maps on every candidate), redone, compared with the "
                          "point-addition pair as a set on every input and discarded")),
    }
    cold_arms = ["cS", "cR", "cRI", "rT"]
    rank_arms = ["kS", "kR", "kRaa", "kRX"]
    rank_blocks = [{"id": "K%d" % (b + 1), "unit": "s%03d" % b, "rank_seed": 201 + b} for b in range(blocks)]
    # Rank blocks spread through the cold panel: O1, then C and K interleaved.
    order = ["O1"]
    per = points // blocks
    for b in range(blocks):
        order += ["C%d" % i for i in range(b * per + 1, (b + 1) * per + 1)] + ["K%d" % (b + 1)]
    order += ["C%d" % i for i in range(blocks * per + 1, points + 1)]
    protocol = {
        "schema": 1,
        "kind": "n83-rankcut-e2e-cold-tier1",
        "frozen_before_any_timing": True,
        "frozen_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "question": ("Does computing the rank stage's partner roots by point addition (x(T+R), x(T-R) from the "
                     "stored root's recovered y and one batched inversion per candidate, instead of the batched "
                     "S3 root solve), with the S3 order resolved exactly at every root-table hit, lower the "
                     "END-TO-END cold cost (setup + index build + rank stage + linear algebra + one-target "
                     "online) of the stacked n=83 K600 producer on new targets and new rank seeds, with every "
                     "rank relation, every per-attempt probe count, every scalar and the factor-log table "
                     "unchanged?"),
        "success_criterion": "AGENTS.md 'Success criterion: iterative improvement of the index-calculus baseline'",
        "current_baseline": ("the stacked producer (koblitz-n83-stacked-20261016, run 38862448935, PR #938): "
                             "end-to-end cold 283.8 s, S 9.68, gap to rT770 94.4 [73.5, 125.3]; its rank stage "
                             "is 257.8 s (91%)"),
        "cost_structure_of_the_baseline": {
            "source": "run 38862448935, arm kS (serials 42 and 116), rank seeds 101 and 102",
            "attempts": 600, "relations": 600, "rank": 600, "rows_without_gain": 0, "failures": 0,
            "policy": "guided: decompose [a]G - R_j for the first pivotless column j; stops at full rank",
            "rank_pdp_share_of_rank_stage": "255,719 of 255,965 ms (99.9%)",
            "mean_probes_per_attempt": 1667423, "ns_per_probe": {"rank": 255.7, "online_same_process": 255.7},
            "reading": ("no attempt is wasted and the stage already stops at full rank, so the number of "
                        "attempts cannot fall; the cost per probe is the lever"),
        },
        "sources": {
            "crypto_770f6a69": "770f6a6925a0d29b768bd79074f54a173e967fe7 (snapshots/r770 via ../koblitz-n83-reconcile-20261014/restore_sources.py)",
            "stacked_producer": ("koblitz-n83-stacked-20261016 make_online_source.py (make_stacked_source.py here, "
                                 "verbatim with its three parents), output sha256 "
                                 "83b589880e5bbd80b2dcf0debf7d20ab268877d4de409c71cf5da17b2f62563c"),
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
            "index_digest": stacked["online"]["index_digest"],
            "factor_log_table": LOG_TABLE,
            "factor_log_table_sha256": sha256(HERE / LOG_TABLE),
            "tuned_rho_config": "snapshots/r770/research/n83_evaluation_20261012/optimization/selected_config.json",
            "cold_targets_file": ("inputs/cold_targets.json (role rankcut-cold-v1; disjoint from Q0, B's panel and "
                                  "every earlier n=83 panel of the law on main, including stacked-cold-v1)"),
            "q0_identity": stacked["online"]["q0_identity"],
            "cold_interval": stacked["online"]["cold_interval"],
            "rank_interval": stacked["online"]["rank_interval"],
            "online_interval": stacked["online"]["online_interval"],
        },
        "arms": arms,
        "design": {
            "cold_points": points,
            "cold_arms": cold_arms,
            "rank_arms": rank_arms,
            "q0_arms": ["cS", "cR"],
            "q0_point": q0,
            "rho_seed_base": 880000,
            "rank_blocks": rank_blocks,
            "rank_blocks_source": "analysis/power.json chosen_rank_blocks",
            "rank_seeds_note": "201.. are new (the stacked run used 101 and 102); each seed fixes 600 new rank targets [a]G - R_j",
            "segment_order": order,
            "within_segment_order": ("random.Random(2026101610 + block).shuffle (C), random.Random(2026101710 + block) (K), "
                                     "random.Random(2026101810) (O)"),
            "process_model": "one point per process, fresh process per run, one pinned CPU, one runner",
            "segment_upper_estimate_s": {"C": 240, "K": 1800, "O": 200},
            "timeout_s": {"ic_cold": 600, "ic_rank": 2400, "rho_tuned": 600},
            "time_guard": "skip a segment (rows skipped_time_guard) if elapsed + its estimate exceeds 300 min",
            "runtime_estimate": ("from run 38862448935: build and tests about 15 min; cold segment about 90 s (cS, cR "
                                 "about 26 s each, cRI about 20 s, rT 3 s); rank block about 1,050 s (kS about 282 s, "
                                 "kR and kRaa about 220 s if the local per-probe ratio holds, kRX about 300 s); "
                                 "%d blocks; total about 2.3 h, up to about 3 h on a slower runner" % blocks),
        },
        "gates": [
            "every scheduled row valid (exit 0, verified, schedule match, no memory event)",
            ("every IC process: lift_scan, Feistel, prefetch; the 16-byte compact table with 2^26 slots over the folded "
             "index (14,940,300 stored of 29,880,000 logical states); 29,878,182 table entries; logical-state blake3 "
             "and table-map digests equal B's (online.index_digest); no root bloom"),
            "per point: one scalar across every IC process (cold and rank) and rT, replayed as [d]G = Q in the pinned oracle",
            "per point: one relation (point indices) and one probe count across every IC process on the point",
            "Q0 (O1): cS and cR give the archived Feistel relation and scalar with 1,987,852 probes",
            ("rank arms: full rank, the arm's KIC_RANK_SOLVE recorded, and the written factor-log table equal to B's "
             "archived table, log for log"),
            ("per rank block: rank_relations_blake3, the per-attempt probe vector (600 entries) and "
             "rank_root_calls_total identical across kS, kR, kRaa and kRX (the candidate keeps every relation and "
             "every probe of the baseline, not only the table)"),
            "kRX: rank_padd_plant_checked_inputs > 0 (every input of its rank stage compared with the S3 roots)",
        ],
        "controls_pass_rule": {
            "aa": ("E2E(kR, cR) / E2E(kRaa, cS) (blocks paired) and cold cR / cS (the same cold code) point "
                   "estimates both inside [0.97, 1.03]"),
            "planted": "rank stage kRX / kR (per-attempt cost, attempts paired within blocks), 95% bootstrap lower bound above 1",
            "otherwise": "verdict invalid",
        },
        "statistics": {
            "end_to_end_cold": ("E2E(k, c) = mean over the rank blocks of timing_ms.rank_stage of rank arm k + mean "
                                "over the cold points of cold_in_process_ms of cold arm c; the cold processes hold "
                                "setup + online, the rank processes the rank stage, so E2E = setup + index build + "
                                "rank stage + linear algebra + one-target online"),
            "primary": ("R = E2E(kS, cS) / E2E(kR, cR). Bootstrap, 10,000 draws, seed 20261016: the rank blocks "
                        "resampled with replacement; within each drawn block the attempt indices resampled with "
                        "replacement and used for both kS and kR (the gate makes attempt i the same target with "
                        "the same probes in both), each process's non-attempt time kept; the cold points "
                        "resampled, paired across cS and cR"),
            "primary_is": "the END-TO-END cold ratio; the rank-stage and online ratios are co-reported and never decide",
            "secondary": [
                "rank stage kS/kR: whole-stage ratio and per-attempt cost ratio (paired bootstrap), ns per probe per arm, kR/kRaa",
                "per-attempt ratio by probe-count tercile (does the gain depend on the attempt length)",
                "cold without rank, setup, online and peak RSS cS/cR (expected 1: same code)",
                "optional component: E2E(kS, cS) / E2E(kR, cRI) and cold cR / cRI (lift_scan in the index build on top of the rank cut)",
                "the point-addition counters per rank process (fallback states, irregular inputs, resolved hits, swapped pairs)",
                "rho ms/step from rT; S = cost / (rho ms/step) / sqrt(r) for E2E cold, cold without rank and online, per arm; delta S cS to cR; E2E cold gap IC / rT and online gaps to rT",
            ],
        },
        "decision_rule": {
            "improvement": "R lower bound > 1 (the rank-cut producer becomes the new n=83 end-to-end cold baseline)",
            "regression": "R upper bound < 1",
            "not_separated": "otherwise",
            "invalid": "any gate or control fails, or any scheduled row is missing (including time-guard skips)",
        },
        "multiplicity": "one primary statistic; every secondary is descriptive and never changes the verdict",
        "exactness_argument": (
            "For points R, T of E(F_2^83) with x(R) != x(T), the two roots of S3(x(R), x(T), X) are x(T + R) and "
            "x(T - R), so the point-addition pair equals the S3 loop's pair as a set. Every stored root is the x "
            "of a point of E (it is x(P1 +- P2)); its y is recovered by the half-trace, and the Frobenius "
            "conjugates (x^(2^s), y^(2^s)) are points of E because E is defined over F_2. The keys are the same "
            "canonical rotations of the same normal-basis values; only the order inside a pair could differ, and "
            "at every root-table hit the S3 pair is recomputed with the S3 solver, asserted equal to the "
            "emitted pair as a set, and the pair is evaluated in the S3 order at the S3 loop's probe positions. "
            "Inputs exceptional for the S3 batch (zero denominator) are solved by the S3 solver itself. So the "
            "first hit, the lift, the relation and the probe count of every attempt are the S3 loop's; the "
            "attempts are a function of the rank seed and the earlier relations, so the echelon and the factor-log "
            "table are the baseline's. Tested on a 9-orbit base (every loop, both orders, a deliberately swapped "
            "emission order) and checked on every input of every kRX rank stage."),
        "power": {"file": "analysis/power.json", "chosen_rank_blocks": blocks, "min_delta": power["min_delta"],
                  "power_at_min_delta": power["power"]["%.2f" % power["min_delta"]]["by_blocks"].get(str(blocks))},
    }
    (HERE / "protocol.json").write_text(json.dumps(protocol, indent=1, sort_keys=True) + "\n")
    print(str(HERE / "protocol.json"))


if __name__ == "__main__":
    main()
