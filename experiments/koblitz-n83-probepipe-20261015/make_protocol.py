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


def ic(canon, order, pipeline, panel_file, role, **extra):
    return dict({"binary": "ic_online_probepipe_r770", "kind": "ic_multi", "canon": canon, "order": order,
                 "pipeline": pipeline, "panel_file": panel_file, "role": role}, **extra)


def main():
    local = json.loads(subprocess.run([sys.executable, str(HERE / "restore.py"), "--print-local-digests"],
                                      check=True, capture_output=True, text=True).stdout)
    derived = HERE / "snapshots/r770/examples/koblitz_orbit_dlp_fast_online_probepipe.rs"
    profiler = HERE / "snapshots/r770/examples/koblitz_orbit_dlp_fast_online_probeprofile.rs"
    power = json.loads((HERE / "analysis/power.json").read_text())
    profile = json.loads((HERE / "analysis/profile_local.json").read_text())
    size = power["chosen_panel_size"]
    arms = {
        "pC": ic("lift", "feistel", "off", "primary",
                 "baseline: the combined producer's probe loop (lift_scan + Feistel order, claude/n83-combined)"),
        "pP": ic("lift", "feistel", "prefetch", "primary",
                 "candidate: combined + software-pipelined root-table probes with prefetch"),
        "pPaa": ic("lift", "feistel", "prefetch", "primary", "A/A control: a second candidate arm"),
        "pX": ic("lift_plus_full", "feistel", "prefetch", "primary",
                 "planted positive control: the candidate plus one discarded full-scan canonicalization per "
                 "partner (claude/n83-combined's planted control), so its probes and relation are pP's and its "
                 "time is known to be larger", planted=True),
        "oC": ic("lift", "feistel", "off", "old17", "secondary/exactness: Q0 + B's 16 fresh points, combined"),
        "oP": ic("lift", "feistel", "prefetch", "old17", "secondary/exactness: Q0 + 16 fresh, candidate"),
        "rT": {"binary": "rho_tuned_r770", "kind": "rho_tuned",
               "role": "A's tuned rho (Fold/64/DP6, crypto 770f6a69; reconcile rT770), the strongest one-target rho "
                       "measured at n=83; one process per primary point; gap reference and scalar cross-check"},
    }
    segment_order = ["P1", "P2", "P3", "O1", "P4", "P5", "P6"]
    protocol = {
        "schema": 1,
        "kind": "n83_probe_pipeline_one_target_online_tier1_v1",
        "question": "On the combined n=83 a=1 K600 one-target IC (lift_scan + Feistel order), does "
                    "software-pipelining the root-table probes of each index state (compute all of the state's "
                    "canonical keys, prefetch every key's home slot, then look them up in the same order) lower the "
                    "one-target online time on new public points, with probes, relation and scalar unchanged?",
        "success_criterion": "AGENTS.md 'Success criterion: iterative improvement of the index-calculus baseline': "
                             "a verified, measured improvement over the current IC baseline under a protocol frozen "
                             "before timing; each landed improvement becomes the new baseline with its delta.",
        "current_baseline": "the combined producer, claude/n83-combined @ 88e1929fb (protocol frozen, run "
                            "38803625711 in flight when this protocol froze; its result is not used here). The "
                            "baseline arm pC is that producer's probe loop byte for byte (make_online_source.py "
                            "checks the combined derivation against its frozen digest and leaves scan_state128 "
                            "unchanged); it runs in the same binary and job as the candidate.",
        "profile": {
            "file": "analysis/profile_local.json",
            "summary": profile.get("summary"),
            "status": "diagnostic, cloud-agent VM; chose the fix, is not evidence of a speedup",
        },
        "arms": arms,
        "design": {
            "host": "one fresh GitHub Actions ubuntu-24.04 runner (Tier 1 instance scope); every run one process pinned "
                    "to one execution CPU (minimum of the affinity mask), clean environment, RAYON/KIC threads 1; "
                    "all arms interleaved in one job; THP as the runner sets it (recorded)",
            "primary_points": size, "slice": 64, "primary_segments": size // 64,
            "primary_ic_arms": ["pC", "pP", "pPaa", "pX"],
            "old17_arms": ["oC", "oP"], "old17_blocks": 1,
            "segment_order": segment_order,
            "within_segment_order": "make_schedule.py's seeded shuffles (P: 2026103100 + s over the four IC "
                                    "processes and the 64 rho runs; O: 2026103300 + b)",
            "rho_seed_base": 850000,
            "rho_seed_rule": "850000 + primary seed",
            "deadline_min": 300,
            "segment_upper_estimate_s": {"P": 1200, "O": 400},
            "timeout_s": {"ic_multi": 2400, "rho_tuned": 300},
            "process_model": "each IC arm is one process per 64-point slice (17 for O): setup (index build, table "
                             "load and verification, bijection self-test) once, then each target with its own "
                             "one-target online interval and no target-dependent work shared between targets",
            "runtime_estimate": "build+tests 20-30 min; log-table check ~2 min; P: 4 x (30-35 s setup + 64 x "
                                "0.2-0.6 s) + 64 rho x 1-3 s = 5-9 min per slice, 6 slices 30-55 min; O: 2 x 1-2 "
                                "min; diagnostic profiler ~2 min; total about 1.0-1.6 h (run 38786433493: IC setup "
                                "29-31 s per process, tuned rho 0.4-3.4 s per process)",
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
                               "phases; the Feistel order, the canonicalizer and the probe pipeline run inside the "
                               "interval; index build, log-table load and verification, the order's bijection "
                               "self-test and process launch are outside",
            "orbit_columns": 600, "regular_states": 29880000,
            "law_probes": LAW_PROBES,
            "law_definition": "r / (A * #states), A = 2n = 166, #states = 29,880,000",
            "q0": ["2655898345537166180532960", "3881526307991673265292615"],
            "q0_validation_scalar_source": "snapshots/r770/experiments/koblitz-single-target-n83-20261006/frozen/fixture.json (fixture_scalar_validation_only), opened only by verify_receipt.py",
            "sqrt_r": 92573139.235,
            "subgroup_order": "8569786107849059",
            "targets_file": "../koblitz-single-target-n83-tier1-20261014/inputs/targets.json",
            "targets_file_sha256": sha256(HERE.parent / "koblitz-single-target-n83-tier1-20261014/inputs/targets.json"),
            "primary_targets_file": "inputs/primary_targets.json (make_targets.py; role probepipe-primary-v1, seeds "
                                    "0..%d; new role, no scalar known, disjoint from Q0, the 16 fresh points, the "
                                    "384 scan-order held-out points and the 576 combined primary points)" % (size - 1),
            "archived_identities_file": "inputs/archived_identities.json (claude/n83-combined, verbatim)",
            "tuned_rho_config": "snapshots/r770/research/n83_evaluation_20261012/optimization/selected_config.json",
        },
        "gates": [
            "isolated_bench Tier 1 counters per run: exit 0, no timeout, verified=1, binary digest unchanged, no "
            "memory events; contention flags recorded and reported, never used to drop rows",
            "every IC process: verified cached table on the frozen base, 29,880,000 states, the requested "
            "canonicalizer, order and probe pipeline reported in summary and every record, no start override, "
            "Feistel bijection self-test passed, full-scan index build, five phases sum to each online interval, "
            "setup ends before the first online interval",
            "primary exactness on every point: pC, pP, pPaa and pX have identical probes and relation",
            "one scalar per primary point across all four IC arms and the tuned rho; every scalar replays as "
            "[d]G = Q in the pinned oracle",
            "Q0 + 16 fresh: oC and oP reproduce the archived Feistel probes and relation (run 38786433493's), "
            "scalars equal the archived ones and replay; Q0 equals the validation sidecar",
        ],
        "statistics": {
            "bootstrap": "random.Random(seed); 10,000 resamples with replacement of the primary points; sorted; 95% "
                         "interval = indices 250 and 9749",
            "primary": "R_m = mean pC / mean pP, online_ms over all %d primary points, seed 2026103500" % size,
            "also_reported": "R_g = gm pC / gm pP (paired geometric mean, seed 2026103501); probe ratio; per-arm "
                             "summaries, ns/probe and mean probes / law; R_m bootstrapped over the 64-point slices "
                             "and per slice (sensitivity, seed 2026103550)",
            "aa": "pP / pPaa, ratio of means, seed 2026103530",
            "planted": "pX / pP, ratio of means, seed 2026103532",
            "rho_gap": "tuned rho / IC for pC and pP on the same primary points, means and geometric means (seeds "
                       "2026103560-2026103563)",
            "S": "S_rho = (mean IC online ms / tuned-rho ms per walk step) / sqrt(r), ms per step = median over "
                 "all rT runs of online_ms / walk_steps; S_probe = mean probes / sqrt(r); for pC and pP, with the "
                 "delta pP - pC",
            "secondaries": "Q0 + 16 fresh: oC / oP on the 16 fresh points (seed 2026103610) and Q0's two times",
        },
        "controls_pass_rule": {"aa": "95% interval inside [0.97, 1.03]", "planted": "95% lower bound > 1"},
        "decision_rule": {
            "primary": "improvement iff the 95% lower bound of R_m exceeds 1; regression iff its upper bound is "
                       "below 1; otherwise not_separated",
            "invalid": "any gate, identity check or control fails, or any primary point lacks a valid row in any "
                       "of the four IC arms or the tuned rho: no verdict; every row is preserved",
            "ratchet": "a primary improvement makes combined + probe pipeline the new n=83 one-target baseline, "
                       "recorded with R_m, R_g, the S_rho delta and the tuned-rho gap",
            "secondaries": "R_g, the slice bootstrap and the Q0 + 16 fresh block are reported; they never change "
                           "the primary verdict or the ratchet",
            "scope": "Tier 1 instance scope, one runner. Not a claim to beat rho: the tuned-rho gap is distance "
                     "remaining.",
        },
        "power": {
            "computed_by": "power_check.py (simulation before freezing; analysis/power.json)",
            "population": "the 384 old held-out targets' measured Feistel full-scan online times (run "
                          "38786433493) over the mean measured full / lift_scan ratio (run 38776966036), "
                          "inputs/power_prior.json; per-point effect spread from the 16 lift_scan ratios; noise "
                          "sigma 0.02 per target and 0.01 per process",
            "chosen_panel_size": size,
            "smallest_powered_size": power["smallest_powered_size"],
            "power_by_size": power["scenarios"],
            "rule": power["power_floor_rule"],
        },
        "multiplicity": "one primary statistic; controls are pass/fail gates; secondaries are reported, never decide",
        "sources": {
            "crypto_770f6a69": "770f6a6925a0d29b768bd79074f54a173e967fe7 (snapshots/r770 via "
                               "../koblitz-n83-reconcile-20261014/restore_sources.py, checked against that "
                               "protocol's r770 digests)",
            "parent": "cryptanalysis claude/n83-combined @ 88e1929fb (make_combined_source.py is its "
                      "make_online_source.py, verbatim; combined producer sha256 f65e518a...)",
            "local_sha256": local,
            "online_source_sha256": sha256(derived),
            "profile_source_sha256": sha256(profiler),
        },
        "frozen_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "frozen_before_any_timing": True,
    }
    (HERE / "protocol.json").write_text(json.dumps(protocol, indent=1, sort_keys=True) + "\n")
    print("protocol_sha256=" + sha256(HERE / "protocol.json"))


if __name__ == "__main__":
    main()
