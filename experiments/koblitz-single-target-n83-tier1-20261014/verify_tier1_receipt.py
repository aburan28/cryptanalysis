#!/usr/bin/env python3
"""Audit a Tier 1 receipt, build and check every vs_rho claim, and apply the frozen decision rule.

Reads the archived receipt directory of one workflow run (allocation,
precompute receipt, the factor-log table and each panel's isolated_bench
output), then, fail-closed:

1. checks each panel's isolated_bench summary, pair order, binaries, noise
   gates and raw arm outputs (the base64 producer records each arm printed);
2. for Panels A and B builds the n=61 harness's vs_rho claim for every pair
   with the pinned `single_target_panel` builder, replays both certificates in
   `oracle.py` and runs `boundary_autolab.validate_claim(stage="vs_rho")`;
3. checks that every recovered scalar on Q0 equals the validation sidecar
   (opened only here);
4. computes the frozen statistics: Panel A median paired ratio with the
   isolated_bench interval and the paired geometric mean; Panel B section 23
   mean ratio with a bootstrap over targets; the cold ratio, break-even count,
   S columns and the Bernstein-Lange model column;
5. applies the decision rule and writes `tier1_result.json` and
   `tier1_table.md` into the receipt directory.

Nothing here is a measurement by itself; it reads the producers' clocks.
"""

import argparse
import base64
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "crypto_source_snapshot"
AUTOLAB = SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"
BL_PRODUCT = 1.93 * 1.21


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def harness():
    sys.path.insert(0, str(AUTOLAB))
    import boundary_autolab as lab  # noqa: E402
    import single_target_panel as panel  # noqa: E402
    return lab, panel


def raw_record(results, row):
    text = (results / row["stdout_file"]).read_text()
    line = next(item for item in text.splitlines() if item.startswith("raw_b64="))
    raw_bytes = base64.b64decode(line.split("=", 1)[1], validate=True)
    if hashlib.sha256(raw_bytes).hexdigest() != row["fields"]["raw_result_sha256"]:
        raise ValueError("raw arm output differs from its recorded digest")
    return json.loads(raw_bytes)


def bootstrap(values, statistic, seed, draws):
    rng = random.Random(seed)
    out = sorted(statistic([values[rng.randrange(len(values))] for _ in values]) for _ in range(draws))
    return [out[int(0.025 * draws)], out[int(0.975 * draws) - 1]]


def reading(interval, eligible):
    if not eligible or interval is None:
        return "no_result"
    if interval[0] > 1:
        return "ic_online_faster"
    if interval[1] < 1:
        return "rho_online_faster"
    return "not_separated"


def audit_panel(name, receipt_dir, protocol):
    summary_path = receipt_dir / ("run-summary_%s.json" % name)
    if not summary_path.exists():
        return {"panel": name, "status": "missing"}
    wrapped = load(summary_path)
    results = Path(wrapped["output"])
    if not results.is_dir():
        results = receipt_dir / "queue" / "results" / results.name
    summary = load(results / "summary.json")
    rows = jsonl(results / "runs.jsonl")
    pairs = jsonl(results / "pairs.jsonl")
    spec = protocol["panels"][name]
    issues = []
    if wrapped["summary"] != summary:
        issues.append("run-summary differs from summary.json")
    if summary.get("measurement_tier") != "tier1_instance":
        issues.append("not a Tier 1 panel")
    if summary.get("status") != "completed" or not summary.get("artifacts_stable"):
        issues.append("isolated_bench did not complete with stable artifacts")
    if summary.get("manifest_sha256") != sha256(results / "manifest.json"):
        issues.append("manifest digest differs")
    if not load(results / "preflight.json").get("ok"):
        issues.append("preflight rejected")
    expected_pairs = spec["targets"] * spec["repetitions"]
    if len(pairs) != expected_pairs or any(p["status"] != "valid" for p in pairs):
        issues.append("pairs incomplete or invalid")
    if any(r["status"] != "valid" or r["issues"] for r in rows):
        issues.append("an arm row is invalid")
    if len({(r["variant"], r["binary_sha256"]) for r in rows}) > 2:
        issues.append("an arm's executable changed within the panel")
    arm_rows = []
    for row in rows:
        if row.get("stdout_file") and (results / row["stdout_file"]).exists():
            try:
                row["_raw"] = raw_record(results, row)
            except (StopIteration, ValueError) as exc:
                issues.append("raw output: %s" % exc)
                row["_raw"] = None
        obs = row.get("tier1_observations") or {}
        deltas = obs.get("counter_deltas") or {}
        if (deltas.get("cpu_stat", {}).get("nr_throttled", 0) or
                deltas.get("memory_events", {}).get("oom", 0) or
                deltas.get("memory_events", {}).get("oom_kill", 0)):
            issues.append("throttling or memory events on serial %s" % row.get("serial"))
        arm_rows.append(row)
    return {"panel": name, "results": str(results), "summary": summary, "rows": arm_rows,
            "pairs": pairs, "issues": issues, "eligible_runner": not issues}


def pair_rows(audit):
    by_serial = {row["serial"]: row for row in audit["rows"]}
    out = []
    for pair in audit["pairs"]:
        if pair["status"] != "valid":
            continue
        ref = by_serial[pair["run_serials"]["reference"]]
        cand = by_serial[pair["run_serials"]["candidate"]]
        out.append({"case": pair["case"], "repeat": pair["repeat"], "rho": ref, "ic": cand,
                    "order": "rho_then_ic" if ref["serial"] < cand["serial"] else "ic_then_rho",
                    "ratio": pair["speedup"]})
    return out


def build_claims(name, pairs, protocol, receipt_dir, precompute, lab, panel, cpu):
    """The n=61 harness's claim for every pair, with its replay and its check."""
    import identity  # noqa: E402  (on sys.path through single_target_panel)
    beats = load(AUTOLAB / "protocol.json")["beats"]
    beat = beats[protocol["harness"]["beat_id"]]
    ledger = lab.load_ledger(lab.load_protocol())
    fixture_base = dict(beat["curve_fixture"])
    curve = panel.cached_curve(fixture_base)
    curve_ids = load(SNAPSHOT / beat["curve_ids"])
    curve_rec = next(c for c in curve_ids["curves"] if (c["a"], c["n"]) == (1, 83))
    header = json.loads((SNAPSHOT / protocol["inputs"]["base"]).read_text().splitlines()[0])
    base_points = [tuple(int(v) for v in p) if p else None for p in header["factor_base_point_coordinates"]]
    representatives = [[int(v) for v in p] for p in header["factor_base_representatives"]]
    hashes = protocol["crypto_source"]["sha256"]
    ic_hashes = {"examples/koblitz_orbit_dlp_fast_online_logcache.rs": hashes["ic_online_patched"],
                 "examples/koblitz_orbit_dlp_fast_online.rs": hashes["ic_online_upstream"],
                 "ic_log_cache.patch": hashes["ic_log_cache_patch"],
                 "crypto_rust_source_tree": hashes["crypto_rust_source_tree"],
                 "factor_log_table": precompute["table_sha256"]}
    rho_hashes = {"examples/koblitz_rho_batch_ks_strong_online.rs": hashes["rho_strong_online"],
                  "crypto_rust_source_tree": hashes["crypto_rust_source_tree"]}
    beat_for_method = dict(beat, panel_producers={"ic": {"source": "examples/koblitz_orbit_dlp_fast_online_logcache.rs"}})
    method = panel.method_record(beat_for_method, 600, curve.r, ic_hashes)
    method["point_decomposition"]["cache_policy"] = (
        "root index rebuilt in every process; factor logs read from the verified once-per-job table")
    method["relation_collection"]["stop_rule"] += "; sequential, run once per job in the precompute step"
    inventory = {"factor_base_orbits": representatives, "columns": len(representatives),
                 "column_convention": "representative"}
    candidate = identity.candidate_manifest(fixture_base | {"targets": []}, inventory, method)
    allocation = load(receipt_dir / "allocation.json")
    envelope = {
        "worker_count": 1, "rayon_threads": 1, "memory_cap": "none",
        "cpus_allowed_list": str(cpu),
        "isolation": "scripts/isolated_bench.py Tier 1 instance runner (GitHub Actions %s); "
                     "host exclusivity unverified" % allocation.get("instance_id"),
        "process": "one process per arm per pair; the IC rebuilds its root index and verifies the cached "
                   "factor logs in every process; rho starts with an empty distinguished-point table",
    }
    interval = {
        "ic_start_event": "target_query_begin: the first operation on the public point, after base, index and "
                          "the verified factor-log table are ready",
        "ic_stop_event": "recovery_check_end: [d]G = Q evaluated in the producer",
        "rho_start_event": "after_target_built: the walk's first start [c]G + Q, after the curve, G-only jump "
                           "table and target point are ready",
        "rho_stop_event": "recovery_check_true: a distinguished-point collision returned d with [d]G = Q",
        "ic_included_stages": ["target_query", "target_PDP", "target_relation_check", "target_descent",
                               "target_recovery_check"],
        "rho_included_stages": ["walk", "collision", "recovery_check"],
        "replay": "both certificates replayed after the run in oracle.py, outside both producers",
    }
    out_dir = receipt_dir / "claims" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    claims = []
    for index, pair in enumerate(pairs):
        ic_record, ic_summary = pair["ic"]["_raw"]["records"]
        rho_record, rho_summary = pair["rho"]["_raw"]["records"]
        point = [int(v) for v in pair["ic"]["_raw"]["point"]]
        tag = "%s_%s_r%d" % (name, pair["case"], pair["repeat"])
        fixture = fixture_base | {"targets": [[str(v) for v in point]], "target_seeds": [pair["case"]],
                                  "target_scalar_constructed": False}
        certificates = {
            "ic": {"arm": "ic", "curve_id": curve_rec["curve_id"], "generator": ic_record["generator"],
                   "target": ic_record["target"], "scalar": ic_record["recovered_scalar"],
                   "relation": {"base_hash": ic_summary["base_hash"], "point_indices": ic_record["point_indices"],
                                "x_codes": [int(v) for v in ic_record["x_codes"]]}},
            "rho": {"arm": "rho", "curve_id": curve_rec["curve_id"], "generator": fixture_base["generator"],
                    "target": rho_record["published_q"], "scalar": rho_record["recovered_fixture_scalar"],
                    "walk_steps": rho_record["walk_steps"]},
        }
        digests, replays = {}, {}
        for arm, cert in certificates.items():
            path = out_dir / ("%s.%s.cert.json" % (tag, arm))
            path.write_bytes(identity.canonical(cert) + b"\n")
            digests[arm] = identity.sha256(cert)
            replays[arm] = panel.replay_certificate(path, digests[arm], fixture,
                                                    base_points if arm == "ic" else None)
        replay_path = out_dir / ("%s.replay.json" % tag)
        replay_path.write_text(json.dumps(replays, indent=2, sort_keys=True) + "\n")
        work = identity.workload_manifest(fixture, input_law=protocol["question"],
                                          algorithm_seed=int(protocol["precompute"]["rank_seed"]),
                                          resource_envelope=envelope, cache_policy="cold")
        run_key = identity.run_id(candidate["candidate_id"], work["workload_id"], index + 1)
        policy = {
            "worker_count": 1,
            "walk_policy": "rung 3: 32 lanes in lockstep, one batched inversion per step; signed-Frobenius class "
                           "representative; 32 r-adding jumps in G; starts [c]G + Q",
            "collision_policy": "distinguished points in one table that starts empty in every process",
            "lanes": 32, "distinguished_point_bits": 4, "rung": 3,
            "distinguished_point_memory_bytes": int(rho_summary["table_payload_lower_bound_bytes"]),
            "seed": int(pair["rho"]["_raw"]["seed"]),
            "automorphism_size": int(rho_record["automorphism_size"]),
        }
        rho_uid = panel.candidate_identity(panel.rho_manifest(curve_rec, policy, rho_hashes))
        ic_ms, rho_ms = float(ic_record["online_ms"]), float(rho_record["online_ms"])
        rank_ms = float(precompute["timing_ms"]["rank_stage"]) + float(precompute["timing_ms"]["linear_algebra"])
        ic_setup_ms = ic_summary["setup_complete_ns"] / 1e6
        target_hash = identity.sha256({"curve_id": curve_rec["curve_id"], "target": point})
        claim = {
            **panel.primary_claim_fields(ic_record, rho_record, interval),
            "schema_version": 2, "beat_id": protocol["harness"]["beat_id"], "stage": "vs_rho",
            "status": "PENDING_INDEPENDENT_VALIDATION", "regime": "koblitz", "result_class": "single_target_online",
            "measurement_tier": "tier1_instance", "panel": name,
            "n_or_bits": {"n": 83, "a": 1, "subgroup_order_bits": round(math.log2(curve.r), 2)},
            "curve_id": curve_rec["curve_id"], "K": 600,
            "candidate_id": candidate["candidate_id"], "candidate_manifest_sha256": candidate["record_sha256"],
            "workload_id": work["workload_id"], "workload_manifest_sha256": work["record_sha256"],
            "run_id": run_key, "rho_reference_uid": rho_uid["candidate_uid"],
            "target_count": 1, "ic_target_hash": target_hash, "rho_target_hash": target_hash,
            "ic_online_phase_ms": {schema: float(ic_record[field]) for schema, field in panel.PHASE_FIELDS.items()},
            "rho_online_phase_ms": {"walk_and_collision_ms": rho_record["walk_and_collision_ms"],
                                    "recovery_check_ms": rho_record["recovery_check_ms"]},
            "online_interval": interval, "same_resource_envelope": True,
            "independent_validation": all(r["statement_holds"] for r in replays.values()),
            "independent_validation_scope": "certificates replayed out of process in oracle.py on the same "
                                            "instance; independent-host replay outstanding",
            "ic_replay_certificate_sha256": digests["ic"], "rho_replay_certificate_sha256": digests["rho"],
            "ic_resource_envelope": envelope, "rho_resource_envelope": dict(envelope),
            "ic_scalar_verified": ic_record["group_verified"] is True and replays["ic"]["statement_holds"],
            "rho_scalar_verified": rho_record["verified"] is True and replays["rho"]["statement_holds"],
            "rho_policy": policy,
            "verdict": "index calculus online faster" if rho_ms > ic_ms else "rho online faster",
            "claim_boundary": "one public point on %s (a=1, n=83); Tier 1 instance-scoped; the IC's reusable "
                              "setup is outside its online interval and is reported beside it" % curve_rec["curve_id"],
            "independent_replay_pointer": str(replay_path.relative_to(receipt_dir)),
            "fixture_hash": identity.sha256(fixture),
            "executable_or_source_hash": {"ic_binary_sha256": pair["ic"]["binary_sha256"],
                                          "rho_binary_sha256": pair["rho"]["binary_sha256"],
                                          "crypto_commit": protocol["crypto_source"]["commit"],
                                          "ic_source_manifest_sha256": identity.sha256(ic_hashes),
                                          "rho_source_manifest_sha256": identity.sha256(rho_hashes)},
            "host_id": {"provider": allocation.get("provider"), "instance_id": allocation.get("instance_id"),
                        "runner_name": allocation.get("runner_name"), "image_version": allocation.get("image_version")},
            "resource_caps": {"rayon_threads": 1, "cpus": envelope["cpus_allowed_list"], "memory": "none"},
            "seeds": {"target": pair["case"], "ic_rank_seed": int(protocol["precompute"]["rank_seed"]),
                      "rho_seed": policy["seed"]},
            "claim_boundary_non_claims": [
                "one public target per row; no multi-target or batch result",
                "the IC's reusable setup (base, index, factor logs, rank stage) is outside its online interval and "
                "is reported beside the claim with the cold ratio",
                "rho has no precomputed distinguished-point table; Bernstein-Lange is a model column, not measured",
                "public synthetic points only; no key recovery; no asymptotic claim",
                "Tier 1 instance-scoped wall time; host exclusivity unverified; independent-host replay outstanding",
            ],
            "cold": {"ic_setup_ms_per_process": ic_setup_ms, "ic_rank_stage_ms_once": rank_ms,
                     "rho_setup_ms": rho_record["online_start_ns"] / 1e6,
                     "ic_cold_ms": ic_setup_ms + rank_ms + ic_ms,
                     "rho_cold_ms": rho_record["online_stop_ns"] / 1e6,
                     "cold_ratio_ic_over_rho": (ic_setup_ms + rank_ms + ic_ms) / (rho_record["online_stop_ns"] / 1e6)},
            "counts": {"ic_probes": ic_record["probes"], "ic_relation_checks": ic_record.get("relation_checks"),
                       "rho_walk_steps": rho_record["walk_steps"]},
            "pair_order": pair["order"],
        }
        validation = lab.validate_claim(claim, stage="vs_rho", ledger=ledger)
        (out_dir / ("%s.claim.json" % tag)).write_text(json.dumps(claim, indent=2, sort_keys=True) + "\n")
        (out_dir / ("%s.claim_check.json" % tag)).write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
        claims.append({"tag": tag, "claim": claim, "check": validation["status"],
                       "errors": validation.get("validation_errors", []) + validation.get("missing_stage_fields", [])})
    return claims


def describe(protocol, curve_r, pairs, precompute, claims=None):
    n = 83
    sqrt_r = math.sqrt(curve_r)
    rows = []
    for pair in pairs:
        ic_record, ic_summary = pair["ic"]["_raw"]["records"][:2]
        rho_record = pair["rho"]["_raw"]["records"][0]
        rows.append({"ic_ms": float(ic_record["online_ms"]),
                     "rho_ms": float(rho_record.get("online_ms") or rho_record.get("total_ms")),
                     "probes": int(ic_record["probes"]), "steps": int(rho_record["walk_steps"]),
                     "ic_setup_ms": ic_summary["setup_complete_ns"] / 1e6,
                     "rho_setup_ms": (rho_record.get("online_start_ns") or 0) / 1e6,
                     "phases": {k: float(ic_record[k]) for k in ("target_query_ms", "target_pdp_ms",
                                "target_relation_check_ms", "target_descent_ms", "target_recovery_check_ms")}})
    rank_ms = float(precompute["timing_ms"]["rank_stage"]) + float(precompute["timing_ms"]["linear_algebra"])
    setup = statistics.median(r["ic_setup_ms"] for r in rows) + rank_ms
    rho_setup = statistics.median(r["rho_setup_ms"] for r in rows)
    c_ms = statistics.median(r["rho_ms"] / r["steps"] for r in rows)
    mean_ic = statistics.fmean(r["ic_ms"] for r in rows)
    mean_rho = statistics.fmean(r["rho_ms"] for r in rows)
    bl_online_ms = BL_PRODUCT * curve_r * c_ms ** 2 / (2 * n * setup)
    floor_steps = math.sqrt(math.pi * curve_r / (4 * n))
    return {
        "pairs": len(rows),
        "median_ic_online_ms": statistics.median(r["ic_ms"] for r in rows),
        "median_rho_online_ms": statistics.median(r["rho_ms"] for r in rows),
        "mean_ic_online_ms": mean_ic, "mean_rho_online_ms": mean_rho,
        "ic_phase_median_ms": {k: statistics.median(r["phases"][k] for r in rows) for k in rows[0]["phases"]},
        "S_ic_online_probes": statistics.fmean(r["probes"] for r in rows) / sqrt_r,
        "S_rho_online_steps": statistics.fmean(r["steps"] for r in rows) / sqrt_r,
        "S_ic_online_in_measured_rho_steps": mean_ic / c_ms / sqrt_r,
        "S_floor_steps": floor_steps / sqrt_r,
        "rho_steps_over_floor_mean": statistics.fmean(r["steps"] for r in rows) / floor_steps,
        "rho_ms_per_step_median": c_ms,
        "ic_setup_ms": {"per_process_median": setup - rank_ms, "rank_stage_once": rank_ms, "total": setup},
        "rho_setup_ms_median": rho_setup,
        "cold_ratio_ic_over_rho": (setup + mean_ic) / (rho_setup + mean_rho),
        "cold_ratio_without_rank_stage": (setup - rank_ms + mean_ic) / (rho_setup + mean_rho),
        "break_even_targets": setup / (mean_rho - mean_ic) if mean_rho > mean_ic else None,
        "bl_model": {"what": "Bernstein-Lange generic walk given the IC's setup as precomputation budget; "
                             "online ~ 1.93*1.21*r*c^2/(2n*P) with c the measured rho ms per step; a model",
                     "bl_online_ms": bl_online_ms, "ic_online_over_bl_model": mean_ic / bl_online_ms},
        "unit_note": "IC probes and rho walk steps are different native units; no common operation S is claimed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt_dir", type=Path)
    args = parser.parse_args()
    receipt_dir = args.receipt_dir.resolve(strict=True)
    protocol = load(HERE / "tier1_protocol.json")
    lab, panel = harness()
    fixture = load(SNAPSHOT / protocol["inputs"]["validation_fixture"])
    sidecar = int(fixture["fixture_scalar_validation_only"])
    precompute = load(receipt_dir / "precompute" / "precompute_receipt.json")
    table = receipt_dir / "precompute" / "factor_logs_n83_K600.json"
    curve_r = int(protocol["curve"]["subgroup_order"])
    result = {"protocol_sha256": sha256(HERE / "tier1_protocol.json"), "precompute": {
        "status": precompute.get("status"), "checks": precompute.get("checks"),
        "table_sha256": precompute.get("table_sha256"), "table_sha256_recomputed": sha256(table) if table.exists() else None,
        "process_wall_s": precompute.get("process_wall_s"), "timing_ms": precompute.get("timing_ms"),
        "max_rss_bytes": precompute.get("max_rss_bytes")}, "panels": {}}
    if precompute.get("status") != "PASS" or result["precompute"]["table_sha256"] != result["precompute"]["table_sha256_recomputed"]:
        result["status"] = "PRECOMPUTE_FAILED"
    for name in ("A", "B", "C"):
        audit = audit_panel(name, receipt_dir, protocol)
        if audit.get("status") == "missing":
            result["panels"][name] = {"status": "missing", "reading": "no_result"}
            continue
        pairs = pair_rows(audit)
        issues = list(audit["issues"])
        for pair in pairs:
            ic_s, rho_s = pair["ic"]["fields"]["recovered_scalar"], pair["rho"]["fields"]["recovered_scalar"]
            if ic_s != rho_s:
                issues.append("arms disagree on %s" % pair["case"])
            if name in ("A", "C") and int(ic_s) != sidecar:
                issues.append("Q0 scalar differs from the validation sidecar")
        entry = {"isolated_bench": {k: audit["summary"].get(k) for k in (
            "status", "valid_pairs", "expected_pairs", "paired_speedup", "tier1_bootstrap95_by_pair",
            "bootstrap95_by_target", "speedup_claim_eligible", "artifacts_stable", "runner_sha256")},
            "issues": issues}
        claims = []
        if name in ("A", "B") and pairs and not audit["issues"]:
            cpu = load(Path(audit["results"]) / "manifest.json")["isolation"]["execution_cpu"]
            claims = build_claims(name, pairs, protocol, receipt_dir, precompute, lab, panel, cpu)
            failing = [c for c in claims if c["check"] != "PASS" or not c["claim"]["independent_validation"]]
            entry["claim_checks"] = {"pass": len(claims) - len(failing), "fail": len(failing),
                                     "failures": [{"tag": c["tag"], "errors": c["errors"]} for c in failing]}
            if failing:
                issues.append("claim check or replay failed")
        if pairs:
            entry["describe"] = describe(protocol, curve_r, pairs, precompute)
        ratios = [p["ratio"] for p in pairs]
        eligible = not issues and len(pairs) == protocol["panels"][name]["targets"] * protocol["panels"][name]["repetitions"]
        if name in ("A", "C"):
            interval = audit["summary"].get("tier1_bootstrap95_by_pair")
            if ratios and interval is not None:
                recomputed = bootstrap(ratios, statistics.median, 20261011, 10000)
                if any(abs(a - b) > 1e-12 for a, b in zip(recomputed, interval)):
                    issues.append("isolated_bench interval does not reproduce")
                    eligible = False
            entry["primary"] = {"statistic": "median rho/IC paired ratio", "value": statistics.median(ratios) if ratios else None,
                                "ci95": interval}
            if ratios:
                logs = [math.log(r) for r in ratios]
                gm_ci = bootstrap(logs, statistics.fmean, 2026101283, 20000)
                entry["secondary_geometric_mean"] = {"value": math.exp(statistics.fmean(logs)),
                                                     "ci95": [math.exp(gm_ci[0]), math.exp(gm_ci[1])]}
        else:
            if pairs:
                values = [(float(p["rho"]["online_ms"]), float(p["ic"]["online_ms"])) for p in pairs]
                stat = lambda sample: statistics.fmean(v[0] for v in sample) / statistics.fmean(v[1] for v in sample)
                interval = bootstrap(values, stat, 2026101400, 10000)
                entry["primary"] = {"statistic": "section 23 mean rho online / mean IC online over targets",
                                    "value": stat(values), "ci95": interval,
                                    "rows_ic_faster": sum(1 for r in ratios if r > 1)}
            else:
                interval = None
        entry["eligible"] = eligible
        entry["reading"] = reading((entry.get("primary") or {}).get("ci95"), eligible)
        if name == "C":
            entry["note"] = "legacy packed rho is not a vs_rho reference; this reading only tests the 2026-10-06 8.2x under isolation"
        result["panels"][name] = entry
    result.setdefault("status", "COMPLETE")
    result["headline"] = {
        "panel_A_reading": result["panels"].get("A", {}).get("reading"),
        "rule": protocol["decision_rule"]["headline_rule"],
    }
    (receipt_dir / "tier1_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    lines = ["| Panel | Pairs | IC online median ms | rho online median ms | primary [95%] | reading | cold ratio IC/rho | IC online / BL model |",
             "|---|---:|---:|---:|---|---|---:|---:|"]
    for name, entry in result["panels"].items():
        d = entry.get("describe") or {}
        p = entry.get("primary") or {}
        ci = p.get("ci95")
        lines.append("| %s | %s | %s | %s | %s %s | %s | %s | %s |" % (
            name, d.get("pairs", 0), fmt(d.get("median_ic_online_ms")), fmt(d.get("median_rho_online_ms")),
            fmt(p.get("value")), "[%s, %s]" % (fmt(ci[0]), fmt(ci[1])) if ci else "",
            entry.get("reading"), fmt(d.get("cold_ratio_ic_over_rho")),
            fmt((d.get("bl_model") or {}).get("ic_online_over_bl_model"))))
    (receipt_dir / "tier1_table.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": result["status"], "readings": {k: v.get("reading") for k, v in result["panels"].items()}},
                     sort_keys=True))


def fmt(value):
    return "%.4g" % value if isinstance(value, (int, float)) else "n/a"


if __name__ == "__main__":
    main()
