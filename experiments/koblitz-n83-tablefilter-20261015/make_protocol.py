#!/usr/bin/env python3
"""Write protocol.json for the root-table filter experiment (used once, to freeze it before any timing).

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


def ic(table, panel_file, role, filter_log2_bits=None, **extra):
    return dict({"binary": "ic_online_tablefilter_r770", "kind": "ic_multi", "canon": "lift", "order": "feistel",
                 "pipeline": "prefetch", "table": table, "filter_log2_bits": filter_log2_bits,
                 "panel_file": panel_file, "role": role}, **extra)


def main():
    local = json.loads(subprocess.run([sys.executable, str(HERE / "restore.py"), "--print-local-digests"],
                                      check=True, capture_output=True, text=True).stdout)
    derived = HERE / "snapshots/r770/examples/koblitz_orbit_dlp_fast_online_tablefilter.rs"
    profiler = HERE / "snapshots/r770/examples/koblitz_orbit_dlp_fast_online_tableprofile.rs"
    power = json.loads((HERE / "analysis/power.json").read_text())
    profile = json.loads((HERE / "analysis/profile_local.json").read_text())
    size = power["chosen_panel_size"]
    arms = {
        "pP": ic("base", "primary",
                 "baseline: the probe-pipeline producer (claude/n83-probe-pipeline: lift_scan + Feistel order + "
                 "prefetched root-table probes) on the 32-byte-slot 4 GiB root table"),
        "pT": ic("filter", "primary",
                 "candidate: pP's scan with the two-level root table: a 32 MiB register-blocked Bloom filter "
                 "(5 bits in one 64-bit word per key) in front of 16-byte exact slots (2 GiB)", 28),
        "pTaa": ic("filter", "primary", "A/A control: a second candidate arm", 28),
        "pX": ic("filter_plant", "primary",
                 "planted positive control: the candidate plus, for every probe the filter rejects, a prefetched "
                 "and discarded lookup of the same key in the compact table (the big-table access the filter "
                 "removes); probes and relation are pT's, every such lookup must find nothing", 28, planted=True),
        "pK": ic("compact", "primary",
                 "secondary/attribution: the 16-byte compact table without the filter (slot size alone)"),
        "pT29": ic("filter", "primary", "secondary/size: the candidate with a 64 MiB filter (2^29 bits)", 29),
        "oP": ic("base", "old17", "secondary/exactness: Q0 + B's 16 fresh points, baseline"),
        "oT": ic("filter", "old17", "secondary/exactness: Q0 + 16 fresh, candidate", 28),
        "rT": {"binary": "rho_tuned_r770", "kind": "rho_tuned",
               "role": "A's tuned rho (Fold/64/DP6, crypto 770f6a69; reconcile rT770), the strongest one-target rho "
                       "measured at n=83; one process per primary point; gap reference and scalar cross-check"},
    }
    segment_order = ["P1", "P2", "P3", "O1", "P4", "P5", "P6"]
    protocol = {
        "schema": 1,
        "kind": "n83_root_table_filter_one_target_online_tier1_v1",
        "question": "On the probe-pipeline n=83 a=1 K600 one-target IC (lift_scan + Feistel order + prefetched "
                    "root-table probes), does a two-level root table (a 32 MiB blocked filter that rejects most "
                    "misses before 16-byte exact slots are touched) lower the one-target online time on new public "
                    "points, with probes, relation and scalar unchanged?",
        "success_criterion": "AGENTS.md 'Success criterion: iterative improvement of the index-calculus baseline': "
                             "a verified, measured improvement over the current IC baseline under a protocol frozen "
                             "before timing; each landed improvement becomes the new baseline with its delta.",
        "current_baseline": "the probe-pipeline producer, claude/n83-probe-pipeline @ ddbb86a9c (protocol frozen, "
                            "run 38822490448 in flight when this protocol froze; its result is not used here). The "
                            "baseline arm pP is that producer's prefetch loop on its 32-byte-slot table "
                            "(make_online_source.py checks the probe-pipeline derivation against its frozen digest "
                            "and leaves scan_state128_pipelined and RootTable128 unchanged); it runs in the same "
                            "binary and job as the candidate. claude/n83-state-fold (run 38819494806, in flight) is "
                            "not included: the filter takes the big table off ~97.6% of probes, so the fold's "
                            "halved capacity no longer bears on the lookup; combining them is a later step.",
        "profile": {
            "file": "analysis/profile_local.json",
            "summary": profile.get("summary"),
            "status": "diagnostic, cloud-agent VM; chose the design, is not evidence of a speedup",
        },
        "arms": arms,
        "design": {
            "host": "one fresh GitHub Actions ubuntu-24.04 runner (Tier 1 instance scope); every run one process pinned "
                    "to one execution CPU (minimum of the affinity mask), clean environment, RAYON/KIC threads 1; "
                    "all arms interleaved in one job; THP as the runner sets it (recorded)",
            "primary_points": size, "slice": 64, "primary_segments": size // 64,
            "primary_ic_arms": ["pP", "pT", "pTaa", "pX", "pK", "pT29"],
            "primary_decision_arms": ["pP", "pT", "pTaa", "pX"],
            "old17_arms": ["oP", "oT"], "old17_blocks": 1,
            "segment_order": segment_order,
            "within_segment_order": "make_schedule.py's seeded shuffles (P: 2026104100 + s over the six IC "
                                    "processes and the 64 rho runs; O: 2026104300 + b)",
            "rho_seed_base": 860000,
            "rho_seed_rule": "860000 + primary seed",
            "deadline_min": 300,
            "segment_upper_estimate_s": {"P": 1500, "O": 400},
            "timeout_s": {"ic_multi": 2400, "rho_tuned": 300},
            "process_model": "each IC arm is one process per 64-point slice (17 for O): setup (index build with "
                             "the arm's table layout and filter, table load and verification, bijection self-test) "
                             "once, then each target with its own one-target online interval and no "
                             "target-dependent work shared between targets",
            "runtime_estimate": "build+tests 20-30 min; log-table check ~2 min; P: 6 x (30-45 s setup + 64 x "
                                "0.15-0.6 s) + 64 rho x 1-3 s = 8-12 min per slice, 6 slices 50-75 min; O: 2 x "
                                "1-2 min; diagnostic profiler ~4 min; total about 1.3-2.0 h",
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
                               "phases; the Feistel order, the canonicalizer, the probe pipeline and the filter "
                               "tests run inside the interval; index build (including the compact table and the "
                               "filter build), log-table load and verification, the order's bijection self-test and "
                               "process launch are outside",
            "orbit_columns": 600, "regular_states": 29880000,
            "root_table_entries": 29878182, "root_table_slots": 134217728,
            "law_probes": LAW_PROBES,
            "law_definition": "r / (A * #states), A = 2n = 166, #states = 29,880,000",
            "q0": ["2655898345537166180532960", "3881526307991673265292615"],
            "q0_validation_scalar_source": "snapshots/r770/experiments/koblitz-single-target-n83-20261006/frozen/fixture.json (fixture_scalar_validation_only), opened only by verify_receipt.py",
            "sqrt_r": 92573139.235,
            "subgroup_order": "8569786107849059",
            "targets_file": "../koblitz-single-target-n83-tier1-20261014/inputs/targets.json",
            "targets_file_sha256": sha256(HERE.parent / "koblitz-single-target-n83-tier1-20261014/inputs/targets.json"),
            "primary_targets_file": "inputs/primary_targets.json (make_targets.py; role tablefilter-primary-v1, seeds "
                                    "0..%d; new role, no scalar known, disjoint from Q0, B's fresh points, the 384 "
                                    "scan-order held-out points, the 576 combined primary points, the 384 "
                                    "probe-pipeline primary points and the 16 state-fold cold points)" % (size - 1),
            "archived_identities_file": "inputs/archived_identities.json (claude/n83-combined, verbatim)",
            "tuned_rho_config": "snapshots/r770/research/n83_evaluation_20261012/optimization/selected_config.json",
        },
        "gates": [
            "isolated_bench Tier 1 counters per run: exit 0, no timeout, verified=1, binary digest unchanged, no "
            "memory events; contention flags recorded and reported, never used to drop rows",
            "every IC process: verified cached table on the frozen base, 29,880,000 states, the requested "
            "canonicalizer, order, probe pipeline, root-table layout and filter size reported in summary and every "
            "record, 29,878,182 root keys in 2^27 slots, KIC_ROOT_BLOOM off, no start override, Feistel bijection "
            "self-test passed, full-scan index build, five phases sum to each online interval, setup ends before "
            "the first online interval",
            "every filter target record: relation checks <= filter passes <= probes; every record: no key the "
            "filter rejected is found in the table (planted_rejected_found = 0; pX looks every rejected key up)",
            "primary exactness on every point: all six IC arms have identical probes and relation",
            "one scalar per primary point across all IC arms and the tuned rho; every scalar replays as "
            "[d]G = Q in the pinned oracle",
            "Q0 + 16 fresh: oP and oT reproduce the archived Feistel probes and relation (run 38786433493's), "
            "scalars equal the archived ones and replay; Q0 equals the validation sidecar",
        ],
        "statistics": {
            "bootstrap": "random.Random(seed); 10,000 resamples with replacement of the primary points; sorted; 95% "
                         "interval = indices 250 and 9749",
            "primary": "R_m = mean pP / mean pT, online_ms over all %d primary points, seed 2026104500" % size,
            "also_reported": "R_g = gm pP / gm pT (paired geometric mean, seed 2026104501); probe ratio; per-arm "
                             "summaries, ns/probe, mean probes / law and filter false-positive rate; R_m "
                             "bootstrapped over the 64-point slices and per slice (sensitivity, seed 2026104550)",
            "aa": "pT / pTaa, ratio of means, seed 2026104530",
            "planted": "pX / pT, ratio of means, seed 2026104532",
            "secondary_arms": "pP / pK (slot size alone, seed 2026104534), pK / pT (the filter over the compact "
                              "table, seed 2026104536), pT / pT29 (filter size, seed 2026104538)",
            "setup_and_cold": "per process: setup_ms (process start to setup complete), index build, filter build, "
                              "peak RSS; per primary point: cold = its slice process's setup + its online time; "
                              "ratios pP / pT of mean setup over the 6 slice processes (reported, no interval) and "
                              "of mean cold over the points (seed 2026104540)",
            "rho_gap": "tuned rho / IC for pP and pT on the same primary points, means and geometric means (seeds "
                       "2026104560-2026104563)",
            "S": "S_rho = (mean IC online ms / tuned-rho ms per walk step) / sqrt(r), ms per step = median over "
                 "all rT runs of online_ms / walk_steps; S_probe = mean probes / sqrt(r); for pP and pT, with the "
                 "delta pT - pP; the cold S_rho (mean cold ms instead of online) is reported too",
            "secondaries": "Q0 + 16 fresh: oP / oT on the 16 fresh points (seed 2026104610) and Q0's two times",
        },
        "controls_pass_rule": {"aa": "95% interval inside [0.97, 1.03]", "planted": "95% lower bound > 1"},
        "decision_rule": {
            "primary": "improvement iff the 95% lower bound of R_m exceeds 1; regression iff its upper bound is "
                       "below 1; otherwise not_separated",
            "invalid": "any gate, identity check or control fails, or any primary point lacks a valid row in any "
                       "of the four decision IC arms (pP, pT, pTaa, pX) or the tuned rho: no verdict; every row is "
                       "preserved. A failed secondary arm (pK, pT29) is reported and does not invalidate",
            "ratchet": "a primary improvement makes probe pipeline + two-level root table the new n=83 one-target "
                       "baseline, recorded with R_m, R_g, the S_rho delta, the cold and setup change and the "
                       "tuned-rho gap",
            "secondaries": "R_g, the slice bootstrap, the attribution and size arms, setup/cold and the Q0 + 16 "
                           "fresh block are reported; they never change the primary verdict or the ratchet",
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
            "parent": "cryptanalysis claude/n83-probe-pipeline @ ddbb86a9c (make_probepipe_source.py is its "
                      "make_online_source.py, verbatim, and make_combined_source.py is claude/n83-combined's; "
                      "probe-pipeline producer sha256 840b1648...)",
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
