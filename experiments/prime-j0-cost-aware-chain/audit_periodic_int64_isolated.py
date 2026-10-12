#!/usr/bin/env python3
"""Fail-closed audit of an isolated 128-bit versus 64-bit periodic panel."""

import argparse
import hashlib
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parent
FIXTURE_SHA256 = "7037c34c8a1a29e58a0831f9767f8828e32d57fa6b18f485e2b26359df46548e"
OPERATION_FIELDS = ("triples", "adds", "rotations", "periodic_lookups",
                    "periodic_accepted", "periodic_fallbacks",
                    "periodic_word_digest", "point_entries", "prep_bytes")


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(receipt):
    fixture_path = ROOT / "periodic-pair-int64-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    manifest = json.loads((receipt / "manifest.json").read_text())
    summary = json.loads((receipt / "summary.json").read_text())
    preflight = json.loads((receipt / "preflight.json").read_text())
    rows = jsonl(receipt / "runs.jsonl")
    pairs = jsonl(receipt / "pairs.jsonl")
    issues = []
    if hashlib.sha256(fixture_path.read_bytes()).hexdigest() != FIXTURE_SHA256:
        issues.append("frozen fixture hash changed")
    if manifest.get("name") != "periodic-pair-int64-isolated-v1" or \
       manifest.get("repetitions") != 5 or len(manifest.get("cases", [])) != 8:
        issues.append("unexpected manifest or repetition count")
    if not preflight.get("ok"):
        issues.append("host isolation preflight failed")
    if summary.get("status") != "completed" or summary.get("valid_pairs") != 40 or \
       summary.get("expected_pairs") != 40:
        issues.append("runner did not complete all 40 pairs")
    for flag in ("artifacts_stable", "binaries_stable", "runner_stable"):
        if summary.get(flag) is not True:
            issues.append(flag + " is not true")
    if len(rows) != 80 or len(pairs) != 40:
        issues.append("raw run or pair count differs from 80/40")
    by_id = {case["id"]: case for case in fixture["cases"]}
    keyed = {(row["case"], row["repeat"], row["variant"]): row for row in rows}
    if len(keyed) != len(rows):
        issues.append("duplicate raw run key")
    ratios = {}
    pair_keys = {(pair["case"], pair["repeat"]): pair for pair in pairs}
    if len(pair_keys) != len(pairs):
        issues.append("duplicate pair key")
    for case_id, case in by_id.items():
        for repeat in range(5):
            try:
                ref = keyed[case_id, repeat, "reference"]
                cand = keyed[case_id, repeat, "candidate"]
            except KeyError:
                issues.append(f"missing arm: {case_id} repeat {repeat}")
                continue
            if ref.get("status") != "valid" or cand.get("status") != "valid":
                issues.append(f"invalid arm: {case_id} repeat {repeat}")
                continue
            for arm in (ref, cand):
                fields = arm["fields"]
                for name, expected in (("curve", case["curve"]["name"]),
                                       ("point_index", str(case["point_index"])),
                                       ("count", "4096"),
                                       ("input_digest", case["input_digest"]),
                                       ("output_digest", case["expected_output_digest"]),
                                       ("verified", "1")):
                    if fields.get(name) != expected:
                        issues.append(f"{case_id} repeat {repeat}: {name} mismatch")
            for name in OPERATION_FIELDS:
                if ref["fields"].get(name) != cand["fields"].get(name):
                    issues.append(f"{case_id} repeat {repeat}: {name} differs")
            pair = pair_keys.get((case_id, repeat))
            if not pair or pair.get("run_serials") != \
               {"reference": ref["serial"], "candidate": cand["serial"]}:
                issues.append(f"{case_id} repeat {repeat}: pair/row serial mismatch")
            if not isinstance(ref.get("metric_ms"), (int, float)) or \
               not isinstance(cand.get("metric_ms"), (int, float)) or \
               ref["metric_ms"] <= 0 or cand["metric_ms"] <= 0:
                issues.append(f"{case_id} repeat {repeat}: invalid online interval")
            else:
                ratios.setdefault(case_id, []).append(ref["metric_ms"] / cand["metric_ms"])
    if any(pair.get("status") != "valid" for pair in pairs):
        issues.append("at least one pair invalid")
    if len(ratios) != 8 or any(len(values) != 5 for values in ratios.values()):
        issues.append("missing complete per-case timing ratios")
    panel_ratio = statistics.median(statistics.median(values) for values in ratios.values()) \
        if not issues else None
    if panel_ratio is not None and (not isinstance(summary.get("paired_speedup"),
                                                   (int, float)) or
                                   abs(panel_ratio - summary["paired_speedup"]) > 1e-12):
        issues.append("reported paired speedup differs from raw rows")
        panel_ratio = None
    result = {"status": "controlled_panel_audited" if not issues else "invalid",
              "case_count": len(by_id), "pair_count": len(pairs),
              "paired_speedup": panel_ratio, "issues": issues}
    print(json.dumps(result, indent=2, sort_keys=True))
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    audit(parser.parse_args().receipt)
