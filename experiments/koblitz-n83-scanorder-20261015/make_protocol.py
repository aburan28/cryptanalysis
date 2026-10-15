#!/usr/bin/env python3
"""Write protocol.json (used once, to freeze the protocol before any timing).

Digests come from `restore.py --print-local-digests` and the derived online
producer; the power figures from `analysis/power.json`; the planted starts
from `inputs/planted_starts.json`. Rerunning it after the freeze would change
`frozen_at_utc`; the committed protocol.json is the frozen record.
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    local = json.loads(subprocess.run([sys.executable, str(HERE / "restore.py"), "--print-local-digests"],
                                      check=True, capture_output=True, text=True).stdout)
    derived = HERE / "snapshots/r770/examples/koblitz_orbit_dlp_fast_online_scanorder.rs"
    power = json.loads((HERE / "analysis/power.json").read_text())
    blocks = json.loads((HERE / "analysis/receipt_blocks.json").read_text())
    ic = lambda order, role, planted=False: dict({"binary": "ic_online_scanorder_r770", "kind": "ic", "order": order,
                                                   "role": role}, **({"planted": True} if planted else {}))
    arms = {
        "qB": ic("left_major", "baseline on Q0: B's pipeline, left-orbit-major state order (unchanged behaviour)"),
        "qP": ic("feistel", "candidate on Q0: keyed Feistel state order"),
        "qBaa": ic("left_major", "A/A control on Q0 (second baseline arm)"),
        "qH": ic("left_major", "planted positive control on Q0: baseline order started halfway through B's own hit-free stretch; exact predicted probes", True),
        "fB": ic("left_major", "baseline on a fresh point"),
        "fP": ic("feistel", "candidate on a fresh point"),
        "fBaa": ic("left_major", "A/A control on a fresh point"),
        "fH": ic("left_major", "planted positive control on a fresh point (half-skip; exact predicted probes)", True),
        "hB": {"binary": "ic_online_scanorder_r770", "kind": "ic_multi", "order": "left_major",
               "role": "held-out secondary panel, baseline order: one process per 64-point slice, one online interval per target"},
        "hP": {"binary": "ic_online_scanorder_r770", "kind": "ic_multi", "order": "feistel",
               "role": "held-out secondary panel, candidate order"},
        "rT": {"binary": "rho_tuned_r770", "kind": "rho_tuned",
               "role": "A's tuned rho (Fold/64/DP6, crypto 770f6a69; reconcile rT770), the strongest one-target rho measured at n=83; gap reference on the same points"},
    }
    protocol = {
        "schema": 1,
        "kind": "n83_scan_order_one_target_online_tier1_v1",
        "question": "Does visiting B's index states in a keyed pseudo-random (Feistel) order instead of left-orbit-major order lower the one-target online cost of the current n=83 K600 cached-log IC baseline, with the same states, the same per-state scan, the same full-scan canonicalizer and the same verified relation semantics?",
        "success_criterion": "AGENTS.md 'Success criterion: iterative improvement of the index-calculus baseline' (branch claude/iterative-success-criterion, PR #919): a verified, measured improvement over the current IC baseline under a protocol frozen before timing; each landed improvement becomes the new baseline with its delta.",
        "finding": "IDEA-20261015-7a3c9e / b41f68 stage 0 (cryptanalysis claude/ic-probe-latency @ cfa806a38, experiments/ic-quotient-law-stage0-20261015): on the 16 fresh points the baseline used 2.30x [0.66, 4.27] the probes of r/(A*#states), CV 1.57, KS p = 0.001; three points at 14.5-18.1M probes.",
        "source_audit": {
            "scan": "crypto 770f6a69 koblitz_orbit_dlp_fast_online.rs, mod wide: build_index128 pushes a state for every (left, right, relative) in that loop order (regular_states = 29,880,000 = 600*600*83); extract128_timed scans states[start..] then states[..start] with start = public-point hash mod S; scan_state128 batch-solves 2n = 166 roots per state and probes 2 partners per root: 332 probes per state, 16,533,600 per left orbit.",
            "receipts": "receipt_blocks.py reconstructs start and hit state of all 17 archived baseline scans (BL arm run 38689817618) from the points and root_calls alone and matches every hit state to its relation's x-codes (17/17). The three tail points ran hit-free for 43,541 (w00), 54,512 (w05) and 53,114 (w13) consecutive states, including w13's whole left block 231; under the geometric law those runs have probability 2.3e-4, 2.8e-5 and 3.7e-5.",
            "mechanism": "every four-term representation of Q is found at the 12 ordered states over its four orbits, 3 in each of its 4 left-orbit blocks, so hit density varies by left block and a left-major scan stays in one block for 16.5M probes. The representation model gives 1.33-1.36x the law for a left-major scan from a uniform start (the K600 rank stage measured 1.40x over 600 relations) and 0.99x for a random order. The model makes three tails in 16 points unlikely (p about 0.002), so either the panel is an unlucky draw or the clustering is stronger than the model; both favour a random order.",
            "hypothesis_status": "the block hypothesis is confirmed in its mechanism (block-aligned hit-free stretches the law cannot produce) and refuted in its arithmetic: not '20% of targets pay a whole extra block' (1 of 16 crossed a whole empty block; 6 of 16 hit past their start block, mostly because their start was near the block's end)",
        },
        "baselines": {
            "online": "B's one-target IC pipeline (experiments/koblitz-single-target-n83-tier1-20261014, run 38523707244; reproduced by koblitz-n83-reconcile-20261014 iB770c and BL-arm run 38689817618): crypto 770f6a69 koblitz_orbit_dlp_fast_online + ic_log_cache.patch, cached verified factor-log table, retained K600 base d4a4da26...a9f7, curve EC1N83Ce1h35c7ced6b497. KIC_SCAN_ORDER=left_major is that code path; the gate requires it to reproduce B's archived probes and relation on all 17 points.",
            "canonicalizer": "the full 83-rotation scan NormalBasis128::canonical in scan_state128, unchanged in every arm (the lift_scan change of claude/n83-liftscan, run 38776966036, is measured separately and is not applied here)",
            "tuned_rho": "rT770, A's configured worker",
            "bl": "precomputation rho (Bernstein-Lange) of run 38689817618 (not rerun here; see external_bl_reference)",
        },
        "arms": arms,
        "design": {
            "host": "one fresh GitHub Actions ubuntu-24.04 runner (Tier 1 instance scope); every run one process pinned to one execution CPU (minimum of the affinity mask), clean environment, RAYON/KIC threads 1",
            "fresh_points": 16, "q0_blocks": 8,
            "q0_ic_arms": ["qB", "qP", "qBaa", "qH"],
            "fresh_ic_arms": ["fB", "fP", "fBaa", "fH"],
            "heldout_arms": ["hB", "hP"], "heldout_points": 384, "heldout_slice": 64, "heldout_segments": 6,
            "heldout_after_f_blocks": [2, 3, 4, 5, 6, 7],
            "order": "Q1, F1, Q2, F2, H1, Q3, F3, H2, ..., Q7, F7, H6, Q8, F8; within-segment orders from make_schedule.py's seeded shuffles",
            "rho_seeds": {"q0": "202610060 + block", "fresh": "830000 + w (B's rule)"},
            "deadline_min": 325,
            "segment_upper_estimate_s": {"Q": 420, "F": 720, "H": 600},
            "timeout_s": {"ic": 900, "ic_multi": 1800, "rho_tuned": 300},
            "runtime_estimate": "build+tests 15-25 min; log-table check ~2 min; Q 32 IC x 40-60 s + 8 rho = 22-33 min; F 64 IC x 40-60 s + 16 rho = 43-65 min; H 12 processes x (35-45 s setup + 64 targets x 0.4-1.5 s) = 12-28 min; total about 1.6-2.6 h (reconcile run 38617911080: cached IC process wall median 41-45 s; tuned rho 2-3 s)",
        },
        "online": {
            "base": "snapshots/r770/experiments/koblitz-single-target-n83-20261006/base_n83_K600.jsonl",
            "base_hash": "d4a4da26d6e7cb09367de922d9806631fe49989f70d378cae76f347f8d76a9f7",
            "curve_id": "EC1N83Ce1h35c7ced6b497",
            "factor_log_table": "../koblitz-single-target-n83-tier1-20261014/tier1_github_38523707244/precompute/factor_logs_n83_K600.json",
            "factor_log_table_sha256": "a771716f284bb826e7407e1e7b5ef882409c9e7e1df8b8a3ed5b60b421d9f17e",
            "factor_log_table_policy": "B's archived table; re-verified before any timing by ../koblitz-n83-reconcile-20261014/verify_log_table.py in the pinned pure-Python oracle; every IC process additionally verifies all [L_j]G = R_j before target work",
            "online_interval": "producer's own clock: target_query_begin .. recovery_check_end, five exclusive phases; the Feistel order is evaluated inside the interval (one evaluation per visited or skipped index); index build, log-table load and verification, the order's bijection self-test and process launch are outside",
            "orbit_columns": 600, "regular_states": 29880000,
            "law_probes": blocks["exact"]["law_probes"],
            "law_definition": "r / (A * #states), A = 2n = 166, #states = 29,880,000",
            "q0": ["2655898345537166180532960", "3881526307991673265292615"],
            "q0_validation_scalar_source": "snapshots/r770/experiments/koblitz-single-target-n83-20261006/frozen/fixture.json (fixture_scalar_validation_only), opened only by verify_receipt.py",
            "sqrt_r": 92573139.235,
            "subgroup_order": "8569786107849059",
            "targets_file": "../koblitz-single-target-n83-tier1-20261014/inputs/targets.json",
            "targets_file_sha256": sha256(HERE.parent / "koblitz-single-target-n83-tier1-20261014/inputs/targets.json"),
            "heldout_targets_file": "inputs/heldout_targets.json (make_heldout_targets.py; role scanorder-heldout, seeds 0..383; no scalar known)",
            "planted_starts_file": "inputs/planted_starts.json (receipt_blocks.py over the archived baseline receipts)",
            "tuned_rho_config": "snapshots/r770/research/n83_evaluation_20261012/optimization/selected_config.json",
        },
        "external_bl_reference": {
            "run": "38689817618 (branch claude/n83-bl-arm @ 4b8ff92a, PR #918), result_table.md",
            "fresh_mean_rho_over_bl": 232.125, "fresh_mean_rho_over_bl_ci95": [125.925, 468.266],
            "fresh_mean_online_ms": {"ic": 1389.91, "bl": 5.91, "rho": 1372.72},
            "q0_median_rho_over_bl": 191.627,
            "use": "derived cross-experiment distance only: IC/BL = (this job's IC/rT) x (that job's rT/BL) on the same 16 points; never a measured row of this job",
        },
        "gates": [
            "isolated_bench Tier 1 counters per run: exit 0, no timeout, verified=1, binary digest unchanged, no memory events; contention flags recorded and reported",
            "every IC process: verified cached table on the frozen base, 29,880,000 states, the requested order and start reported in summary and record, Feistel bijection self-test passed, full-scan index build, five phases sum to the online interval, setup ends before the online interval",
            "left-major arms (qB, qBaa, fB, fBaa) reproduce B's archived probes and relation on every point",
            "planted arms (qH, fH) report exactly the predicted probes and B's relation",
            "one scalar per point across every IC arm and the tuned rho; every scalar replays as [d]G = Q in the pinned oracle; Q0's scalar equals the validation sidecar",
            "held-out panel: hB and hP recover the same scalar for every seed and each replays in the oracle",
        ],
        "statistics": {
            "bootstrap": "random.Random(seed); 10,000 resamples with replacement of the units; statistic recomputed per resample; sorted; 95% interval = indices 250 and 9749",
            "primary": "fresh: section 23 ratio of means, mean over B's 16 fresh points of fB online_ms / mean of fP online_ms; bootstrap over points, seed 2026101500",
            "fresh_secondaries": "ratio of geometric means (paired, seed 2026101501); median per-point ratio (2026101502); section 23 on probes (2026101503); per-arm geometric mean, mean, CV of online_ms and probes with bootstrap, and mean probes / law",
            "fresh_aa": "fB / fBaa, section 23, seed 2026101504",
            "fresh_planted": "fB / fH, section 23, seed 2026101505 (expected about 2 by construction)",
            "q0": "per block qB/qP, qB/qBaa, qB/qH; median of the 8 block ratios; seeds 2026101550-52 (one target: timing and repeat variation only)",
            "heldout": "384 held-out points: section 23 ratio of means hB/hP over targets (seed 2026101560), ratio of geometric means (2026101561), section 23 on probes (2026101562), per-arm summaries and mean probes / law",
            "rho_gap": "Q0 per block rT/qB and rT/qP (median, seeds 2026101590/91); fresh section 23 mean rT / mean fB and / mean fP (2026101592/93) and geometric-mean ratios (2026101594/95)",
            "S": "S_probe = probes / sqrt(r); S_rho = (IC online ms / tuned-rho ms per walk step) / sqrt(r), ms per step = median over all rT runs of online_ms / walk_steps; for baseline and candidate on Q0 (median), fresh (mean) and held-out (mean), with deltas",
            "bl_gap": "derived (external_bl_reference); reported, never decides",
        },
        "controls_pass_rule": {"aa": "95% interval inside [0.97, 1.03] (fresh and Q0)",
                               "planted": "95% lower bound > 1 (fresh and Q0)"},
        "decision_rule": {
            "primary": "the user's rule: an improvement iff the fresh primary's 95% lower bound > 1 on online time over the 16 points; regression iff its upper bound < 1; otherwise not_separated",
            "invalid": "any gate, identity check or control (fresh or Q0 A/A, fresh or Q0 planted) fails, or a fresh point is missing: no verdict; every row is preserved",
            "ratchet": "a primary improvement makes the Feistel-order pipeline the new one-target baseline, recorded with the ratio, the S_rho delta and the tuned-rho and BL gaps",
            "secondaries": "Q0 and the held-out panel are classified with the same interval rule and reported; they never change the primary verdict or the ratchet",
            "scope": "Tier 1 instance scope, one runner. Not a claim to beat rho: the tuned-rho and BL gaps are distance remaining.",
        },
        "power": {
            "computed_by": "power_check.py (model, before freezing; analysis/power.json)",
            "primary_16_points": power["primary_16_fresh_points"]["power"],
            "heldout_384_points": power["heldout_384_points"]["power"],
            "reading": "B's archived 16-point baseline mean is dominated by three tail points, so the bootstrap over 16 points has a wide interval: at the predicted effect (candidate ~ Exp(law)) the primary's lower bound exceeds 1 in about 11% of simulated experiments. A not_separated primary is therefore the expected outcome even if the fix works as modelled. The 384-point held-out panel (new points, not the ones that motivated the hypothesis, so free of the selection that inflates the 16-point gain) has about 94% power at the model's 1.33x. It is pre-registered as a secondary because the primary rule is the user's.",
            "selection_bias": "the 16 fresh points are the panel on which the anomaly was found; their baseline mean is 2.30x the law against the model's 1.33x, so the 16-point ratio is expected to overstate the gain on new targets; the held-out ratio is the unbiased estimate",
        },
        "multiplicity": "one primary; controls are pass/fail gates; secondaries are reported, never decide",
        "sources": {
            "crypto_770f6a69": "770f6a6925a0d29b768bd79074f54a173e967fe7 (snapshots/r770 via ../koblitz-n83-reconcile-20261014/restore_sources.py, checked against that protocol's r770 digests)",
            "local_sha256": local,
            "online_source_sha256": sha256(derived),
            "bl_receipts_sha256": {r["point_id"]: r["receipt_sha256"] for r in blocks["rows"]},
        },
        "frozen_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "frozen_before_any_timing": True,
    }
    (HERE / "protocol.json").write_text(json.dumps(protocol, indent=1, sort_keys=True) + "\n")
    print("protocol_sha256=" + sha256(HERE / "protocol.json"))


if __name__ == "__main__":
    main()
