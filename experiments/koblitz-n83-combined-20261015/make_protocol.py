#!/usr/bin/env python3
"""Write protocol.json (used once, to freeze the protocol before any timing).

Digests come from `restore.py --print-local-digests` and the derived online
producer; the power figures and the panel size from `analysis/power.json`.
Rerunning it after the freeze would change `frozen_at_utc`; the committed
protocol.json is the frozen record.
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAW_PROBES = 8569786107849059 / (2 * 83 * 29880000)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ic(canon, order, panel_file, role, **extra):
    return dict({"binary": "ic_online_combined_r770", "kind": "ic_multi", "canon": canon, "order": order,
                 "panel_file": panel_file, "role": role}, **extra)


def main():
    local = json.loads(subprocess.run([sys.executable, str(HERE / "restore.py"), "--print-local-digests"],
                                      check=True, capture_output=True, text=True).stdout)
    derived = HERE / "snapshots/r770/examples/koblitz_orbit_dlp_fast_online_combined.rs"
    power = json.loads((HERE / "analysis/power.json").read_text())
    size = power["chosen_panel_size"]
    arms = {
        "pB": ic("full", "left_major", "primary", "B: the pre-improvement pipeline (full scan, left-major order)"),
        "pL": ic("lift", "left_major", "primary", "single arm 1: lift_scan canonicalizer only (PR #926, run 38776966036)"),
        "pF": ic("full", "feistel", "primary", "single arm 2: Feistel scan order only (PR #927, run 38786433493)"),
        "pLF": ic("lift", "feistel", "primary", "candidate: lift_scan + Feistel order"),
        "pLFaa": ic("lift", "feistel", "primary", "A/A control: a second candidate arm"),
        "pX": ic("lift_plus_full", "feistel", "primary",
                 "planted positive control: the candidate plus one discarded full-scan canonicalization per partner "
                 "(the per-probe work lift_scan removed), so its probes and relation are pLF's and its time is known "
                 "to be larger", planted=True),
        "hB": ic("full", "left_major", "old_heldout", "secondary: old 384 held-out panel, B"),
        "hL": ic("lift", "left_major", "old_heldout", "secondary: old held-out, lift_scan only"),
        "hF": ic("full", "feistel", "old_heldout", "secondary: old held-out, Feistel only"),
        "hLF": ic("lift", "feistel", "old_heldout", "secondary: old held-out, combined"),
        "oB": ic("full", "left_major", "old17", "secondary: Q0 + B's 16 fresh points, B"),
        "oL": ic("lift", "left_major", "old17", "secondary: Q0 + 16 fresh, lift_scan only"),
        "oF": ic("full", "feistel", "old17", "secondary: Q0 + 16 fresh, Feistel only"),
        "oLF": ic("lift", "feistel", "old17", "secondary: Q0 + 16 fresh, combined"),
        "rT": {"binary": "rho_tuned_r770", "kind": "rho_tuned",
               "role": "A's tuned rho (Fold/64/DP6, crypto 770f6a69; reconcile rT770), the strongest one-target rho "
                       "measured at n=83; one process per primary point; gap reference and scalar cross-check"},
    }
    segment_order = ["P1", "H1", "P2", "H2", "P3", "O1", "P4", "H3", "P5", "H4", "P6", "O2", "P7", "H5", "P8",
                     "H6", "P9"]
    protocol = {
        "schema": 1,
        "kind": "n83_combined_liftscan_feistel_one_target_online_tier1_v1",
        "question": "Does the combination of the two measured, promoted n=83 K600 one-target IC improvements, the "
                    "lift_scan target canonicalizer (cuts ns/probe, probes unchanged) and the Feistel scan order "
                    "(cuts probes), lower the one-target online time below the better of the two single changes, on "
                    "new public points?",
        "success_criterion": "AGENTS.md 'Success criterion: iterative improvement of the index-calculus baseline' "
                             "(PR #919): a verified, measured improvement over the current IC baseline under a protocol "
                             "frozen before timing; each landed improvement becomes the new baseline with its delta.",
        "current_baseline": "the two single improvements were each measured against B with the other factor at "
                            "baseline (lift_scan: PR #926, branch claude/n83-liftscan @ 8f6b4057e, run 38776966036, "
                            "online 1.515 [1.506, 1.525] on B's 16 fresh points; Feistel: PR #927, branch "
                            "claude/n83-scan-order @ af41562e7, run 38786433493, held-out 384 ratio of means 1.45 "
                            "[1.20, 1.74]). Neither was measured with the other, so the incumbent here is the better "
                            "single arm on this panel, decided inside every bootstrap resample.",
        "arms": arms,
        "design": {
            "host": "one fresh GitHub Actions ubuntu-24.04 runner (Tier 1 instance scope); every run one process pinned "
                    "to one execution CPU (minimum of the affinity mask), clean environment, RAYON/KIC threads 1; "
                    "all arms interleaved in one job",
            "primary_points": size, "slice": 64, "primary_segments": size // 64,
            "primary_ic_arms": ["pB", "pL", "pF", "pLF", "pLFaa", "pX"],
            "old_heldout_arms": ["hB", "hL", "hF", "hLF"], "old_heldout_points": 384, "old_heldout_segments": 6,
            "old17_arms": ["oB", "oL", "oF", "oLF"], "old17_blocks": 2,
            "segment_order": segment_order,
            "within_segment_order": "make_schedule.py's seeded shuffles (P: 2026102100 + s over the six IC "
                                    "processes and the 64 rho runs; H: 2026102200 + h; O: 2026102300 + b)",
            "rho_seed_base": 840000,
            "rho_seed_rule": "840000 + primary seed",
            "deadline_min": 325,
            "segment_upper_estimate_s": {"P": 1500, "H": 700, "O": 400},
            "timeout_s": {"ic_multi": 2400, "rho_tuned": 300},
            "process_model": "each IC arm is one process per 64-point slice (17 for O): setup (index build, table "
                             "load and verification, bijection self-test) once, then each target with its own "
                             "one-target online interval and no target-dependent work shared between targets",
            "runtime_estimate": "build+tests 20-30 min; log-table check ~2 min; P: 6 x (30-35 s setup + 64 x "
                                "0.3-0.9 s) + 64 rho x 1-3 s = 8-13 min per slice, 9 slices 75-115 min; H: 4 x "
                                "(30-35 s + 64 x 0.4-0.9 s) = 4-6 min per slice, 6 slices 25-35 min; O: 2 x 3-4 min; "
                                "total about 2.2-3.2 h (run 38786433493: IC setup 29-31 s per process, tuned rho "
                                "0.4-3.4 s per process, held-out processes 66-93 s for 64 targets)",
        },
        "online": {
            "base": "snapshots/r770/experiments/koblitz-single-target-n83-20261006/base_n83_K600.jsonl",
            "base_hash": "d4a4da26d6e7cb09367de922d9806631fe49989f70d378cae76f347f8d76a9f7",
            "curve_id": "EC1N83Ce1h35c7ced6b497",
            "factor_log_table": "../koblitz-single-target-n83-tier1-20261014/tier1_github_38523707244/precompute/factor_logs_n83_K600.json",
            "factor_log_table_sha256": "a771716f284bb826e7407e1e7b5ef882409c9e7e1df8b8a3ed5b60b421d9f17e",
            "factor_log_table_policy": "B's archived table; re-verified before any timing by "
                                       "../koblitz-n83-reconcile-20261014/verify_log_table.py in the pinned "
                                       "pure-Python oracle; every IC process additionally verifies all [L_j]G = R_j "
                                       "before target work",
            "online_interval": "producer's own clock: target_query_begin .. recovery_check_end, five exclusive "
                               "phases; the Feistel order and the canonicalizer run inside the interval; index "
                               "build, log-table load and verification, the order's bijection self-test and "
                               "process launch are outside",
            "orbit_columns": 600, "regular_states": 29880000,
            "law_probes": LAW_PROBES,
            "law_definition": "r / (A * #states), A = 2n = 166, #states = 29,880,000",
            "q0": ["2655898345537166180532960", "3881526307991673265292615"],
            "q0_validation_scalar_source": "snapshots/r770/experiments/koblitz-single-target-n83-20261006/frozen/fixture.json (fixture_scalar_validation_only), opened only by verify_receipt.py",
            "sqrt_r": 92573139.235,
            "subgroup_order": "8569786107849059",
            "targets_file": "../koblitz-single-target-n83-tier1-20261014/inputs/targets.json",
            "targets_file_sha256": sha256(HERE.parent / "koblitz-single-target-n83-tier1-20261014/inputs/targets.json"),
            "primary_targets_file": "inputs/primary_targets.json (make_targets.py; role combined-primary-v1, seeds "
                                    "0..%d; new role, no scalar known, disjoint from Q0, the 16 fresh points and "
                                    "the 384 old held-out points)" % (size - 1),
            "old_heldout_targets_file": "inputs/old_heldout_targets.json (role scanorder-heldout, seeds 0..383; "
                                        "regenerated and compared by make_targets.py)",
            "archived_identities_file": "inputs/archived_identities.json",
            "tuned_rho_config": "snapshots/r770/research/n83_evaluation_20261012/optimization/selected_config.json",
        },
        "gates": [
            "isolated_bench Tier 1 counters per run: exit 0, no timeout, verified=1, binary digest unchanged, no "
            "memory events; contention flags recorded and reported, never used to drop rows",
            "every IC process: verified cached table on the frozen base, 29,880,000 states, the requested "
            "canonicalizer and order reported in summary and every record, no start override, Feistel bijection "
            "self-test passed, full-scan index build, five phases sum to each online interval, setup ends before "
            "the first online interval",
            "primary exactness on every point: pL reproduces pB's probes and relation; pF, pLF, pLFaa and pX have "
            "identical probes and relation (lift_scan is exact, so the canonicalizer never changes the search)",
            "one scalar per primary point across all six IC arms and the tuned rho; every scalar replays as "
            "[d]G = Q in the pinned oracle",
            "old panels: every left-major arm reproduces the archived left-major probes and relation, every "
            "Feistel arm the archived Feistel ones, on Q0, the 16 fresh points and all 384 old held-out points; "
            "scalars equal the archived ones and replay; Q0 equals the validation sidecar",
        ],
        "statistics": {
            "bootstrap": "random.Random(seed); 10,000 resamples with replacement of the primary points; the "
                         "statistic is recomputed per resample, including which single arm is better; sorted; 95% "
                         "interval = indices 250 and 9749",
            "primary": "R_m = min(mean pL, mean pF) / mean pLF (ratio of means) and R_g = min(gm pL, gm pF) / gm "
                       "pLF (ratio of geometric means), online_ms over all %d primary points; seeds 2026102500 and "
                       "2026102501" % size,
            "also_reported": "combined vs each single arm and vs B (means and geometric means, seeds "
                             "2026102510-2026102519), probe ratios, per-arm summaries and mean probes / law; a "
                             "bootstrap of R_m over the 64-point slices (sensitivity to process-level effects, seed "
                             "2026102550)",
            "aa": "pLF / pLFaa, ratio of means, seed 2026102530",
            "planted": "pX / pLF, ratio of means, seed 2026102532",
            "rho_gap": "tuned rho / IC per arm on the same primary points, means and geometric means (seeds "
                       "2026102560-2026102567)",
            "S": "S_rho = (mean IC online ms / tuned-rho ms per walk step) / sqrt(r), ms per step = median over "
                 "all rT runs of online_ms / walk_steps; S_probe = mean probes / sqrt(r); for pB, pL, pF and pLF, "
                 "with the delta of pLF against the better single arm and against B",
            "secondaries": "old 384 held-out panel: R_m, R_g and combined vs B (seeds 2026102600-2026102607); "
                           "Q0 + 16 fresh: block-1 R_m, R_g and combined vs B (2026102610-2026102613), Q0 per-block "
                           "times and probes",
        },
        "controls_pass_rule": {"aa": "95% interval inside [0.97, 1.03]", "planted": "95% lower bound > 1"},
        "decision_rule": {
            "primary": "improvement iff the 95% lower bounds of both R_m and R_g exceed 1; regression iff both upper "
                       "bounds are below 1; otherwise not_separated",
            "invalid": "any gate, identity check or control fails, or any primary point lacks a valid row in any "
                       "of the six IC arms or the tuned rho: no verdict; every row is preserved",
            "ratchet": "a primary improvement makes the lift_scan + Feistel pipeline the new n=83 one-target "
                       "baseline, recorded with R_m, R_g, the S_rho delta and the tuned-rho gap",
            "secondaries": "the old panels, combined vs B and the slice bootstrap are reported with the same "
                           "interval rule; they never change the primary verdict or the ratchet",
            "scope": "Tier 1 instance scope, one runner. Not a claim to beat rho: the tuned-rho gap is distance "
                     "remaining.",
        },
        "power": {
            "computed_by": "power_check.py (simulation before freezing; analysis/power.json)",
            "population": "the 384 old held-out targets' measured left-major and Feistel full-scan online times "
                          "(run 38786433493) and the 16 per-point full / lift_scan ratios (run 38776966036), "
                          "inputs/power_prior.json; timing noise sigma 0.02",
            "chosen_panel_size": size,
            "power_at_chosen_size": power["scenarios"]["measured"]["power"][str(size)],
            "stress_scenario_at_chosen_size": power["scenarios"]["shrunk"]["power"][str(size)],
            "rule": power["power_floor_rule"],
            "reading": "R_m is powered near 1 at every size tried; R_g, the geometric-mean ratio, is the binding "
                       "statistic (expected 1.27 against 1.45 for R_m), so the panel is sized for the rule's "
                       "conjunction. If the order effect were only 1.30 on means (stress scenario) the rule would "
                       "have much lower power; that scenario is reported, not sized for.",
        },
        "multiplicity": "one primary (a conjunction of two bounds, which only lowers the false-improvement rate); "
                        "controls are pass/fail gates; secondaries are reported, never decide",
        "sources": {
            "crypto_770f6a69": "770f6a6925a0d29b768bd79074f54a173e967fe7 (snapshots/r770 via "
                               "../koblitz-n83-reconcile-20261014/restore_sources.py, checked against that "
                               "protocol's r770 digests)",
            "parents": {"liftscan": "cryptanalysis claude/n83-liftscan @ 8f6b4057e (PR #926)",
                        "scan_order": "cryptanalysis claude/n83-scan-order @ af41562e7 (PR #927)"},
            "local_sha256": local,
            "online_source_sha256": sha256(derived),
        },
        "frozen_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "frozen_before_any_timing": True,
    }
    (HERE / "protocol.json").write_text(json.dumps(protocol, indent=1, sort_keys=True) + "\n")
    print("protocol_sha256=" + sha256(HERE / "protocol.json"))


if __name__ == "__main__":
    main()
