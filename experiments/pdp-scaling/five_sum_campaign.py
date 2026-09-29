#!/usr/bin/env python3
"""Freeze and run a bounded exact five-summand MITM on archived subgroup bases."""

import argparse
import hashlib
import json
import lzma
from pathlib import Path
import platform
import random
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gf2n import Curve, GF2n, INF, Point
from groebner_compare.relation_metrics import RelationRank

HERE = Path(__file__).resolve().parent
ARCHIVES = HERE / "explicit-base-frontier-20260928"
NATIVE = HERE / "five_sum_mitm.cpp"
SOURCE = HERE / "explicit_base_frontier.cpp"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mul(curve, point, k):
    result = INF
    while k:
        if k & 1:
            result = curve.add(result, point)
        point = curve.add(point, point)
        k >>= 1
    return result


def rows(path):
    data = lzma.decompress(path.read_bytes())
    parsed = [json.loads(line) for line in data.splitlines()]
    if not parsed or parsed[-1].get("summary") is not True:
        raise ValueError("incomplete base archive")
    return parsed[:-1], parsed[-1]


def make_case(n, l, signed_limit, count, seed):
    freeze_start = time.monotonic()
    run = ARCHIVES / ("run-1" if n == 13 else "run-2")
    path = run / f"n{n}-l{l}.jsonl.xz"
    archive = json.loads((run / "archives.json").read_text())[path.name]
    if path.stat().st_size != archive["bytes"] or sha(path) != archive["sha256"]:
        raise ValueError("base archive digest mismatch")
    base_record = json.loads((HERE / "ordinary-evidence-20260928" / f"n{n}.json").read_text())["base"]
    original, summary = rows(path)
    reps = sorted({(int(r["projected_x"], 16), int(r["projected_y"], 16)) for r in original})
    if len(reps) * 2 != summary["signed_projected_B"] or signed_limit > 2 * len(reps):
        raise ValueError("incorrect archived base count or subset width")
    if signed_limit % 2:
        raise ValueError("subset must include both signs")
    modulus = base_record["modulus"]
    curve = Curve(GF2n(n, modulus), 1)
    chosen = reps[:signed_limit // 2]
    points = [Point(x, y) for x, y in chosen]
    points += [curve.neg(p) for p in points]
    if len(set(points)) != signed_limit or not all(curve.on_curve(p) for p in points):
        raise ValueError("duplicate or invalid subset point")
    generator = points[0]
    r = base_record["subgroup_order"]
    if mul(curve, generator, r) != INF:
        raise ValueError("generator outside claimed subgroup")
    rng = random.Random(seed)
    queries = []
    target_start = time.monotonic()
    for _ in range(count):
        scalar = rng.randrange(1, r)
        target = mul(curve, generator, scalar)
        queries.append({"target": [hex(target.x), hex(target.y)],
                        "audit_scalar": str(scalar)})
    target_generation_seconds = time.monotonic() - target_start
    planted = curve.sum(points[i] for i in (0, 1, 2, 3, 4))
    if planted == INF:
        raise ValueError("degenerate planted control")
    original_receipts = json.loads((run / "results.json").read_text())["results"]
    base_seconds = next(r["base_preparation_seconds"] for r in original_receipts
                        if r["n"] == n and r["l"] == l)
    return {"n": n, "l": l, "modulus": str(modulus), "subgroup_order": str(r),
            "base_archive": str(path.relative_to(ROOT)), "archive_sha256": sha(path),
            "full_signed_B": summary["signed_projected_B"], "signed_subset": signed_limit,
            "subset_rule": "first signed_limit/2 canonical representatives in (x,y) order, then their negatives",
            "seed": seed, "queries": queries,
            "full_base_preparation_seconds": base_seconds,
            "target_generation_seconds": target_generation_seconds,
            "freeze_construction_seconds": time.monotonic() - freeze_start,
            "planted_control": [hex(planted.x), hex(planted.y)]}


def freeze(output):
    manifest = {"schema": "five-sum-mitm-v1", "stage": "subset PDP diagnostic",
                "candidate_id": None, "source_sha256": {
                    str(p.relative_to(ROOT)): sha(p) for p in (NATIVE, SOURCE, Path(__file__))},
                "cases": [make_case(13, 5, 26, 24, 210013),
                          make_case(83, 17, 128, 4, 210083)],
                "max_triples_per_target": 50000, "max_seconds_per_target": 5,
                "pair_entry_cap": 1500000, "address_space_mib": 512,
                "status_rule": "exhausted only after all subset triples; budget otherwise",
                "claim_rule": "subset results are not full-base natural yield; controls excluded from throughput"}
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"manifest": str(output), "sha256": sha(output)}))


def run(manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    for name, digest in manifest["source_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"source changed: {name}")
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_bytes(manifest_path.read_bytes())
    subprocess.run(["g++", "-std=c++17", "-O3", "-Wall", "-Wextra", "-Werror", str(NATIVE),
                    "-o", str(output / "five_sum_mitm")], check=True, capture_output=True, timeout=60)
    host = {"platform": platform.platform(), "compiler": subprocess.check_output(
        ["g++", "--version"], text=True).splitlines()[0], "binary_sha256": sha(output / "five_sum_mitm")}
    (output / "host.json").write_text(json.dumps(host, indent=2) + "\n")
    receipts = []
    for case in manifest["cases"]:
        input_start = time.monotonic()
        n, l = case["n"], case["l"]
        raw, summary = rows(ROOT / case["base_archive"])
        if sha(ROOT / case["base_archive"]) != case["archive_sha256"] or summary["signed_projected_B"] != case["full_signed_B"]:
            raise ValueError("frozen base changed")
        reps = sorted({(int(p["projected_x"], 16), int(p["projected_y"], 16)) for p in raw})
        curve = Curve(GF2n(n, int(case["modulus"])), 1)
        subset = [Point(x, y) for x, y in reps[:case["signed_subset"] // 2]]
        subset += [curve.neg(p) for p in subset]
        prefix = output / f"n{n}-l{l}"
        base_tsv = prefix.with_suffix(".base.tsv")
        base_tsv.write_text("".join(f"{p.x:x} {p.y:x}\n" for p in subset))
        public_tsv = prefix.with_suffix(".targets.tsv")
        public_tsv.write_text("".join(f"{int(q['target'][0],16):x} {int(q['target'][1],16):x}\n"
                                      for q in case["queries"]))
        input_loading_seconds = time.monotonic() - input_start
        def restrict():
            limit = manifest["address_space_mib"] * 1024**2
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        def execute(inputs, expected, label, summands=5):
            cmd = [str(output / "five_sum_mitm"), str(n), case["modulus"], str(base_tsv),
                   str(inputs), str(manifest["max_triples_per_target"]),
                   str(manifest["max_seconds_per_target"]), str(expected), str(summands)]
            t = time.monotonic()
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, preexec_fn=restrict,
                                   timeout=expected * (manifest["max_seconds_per_target"] + 3) + 20)
                exit_code = p.returncode
                stdout, stderr = p.stdout, p.stderr
            except subprocess.TimeoutExpired as exc:
                exit_code = None
                stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout or ""
                stderr = "watchdog timeout"
            (output / f"n{n}-l{l}.{label}.jsonl").write_text(stdout)
            (output / f"n{n}-l{l}.{label}.stderr").write_text(stderr)
            return exit_code, [json.loads(line) for line in stdout.splitlines()], time.monotonic() - t
        planted_tsv = prefix.with_suffix(".control.tsv")
        planted_tsv.write_text(f"{int(case['planted_control'][0],16):x} {int(case['planted_control'][1],16):x}\n")
        control_code, control, control_wall = execute(planted_tsv, 1, "control")
        code, results, wall = execute(public_tsv, len(case["queries"]), "ordinary")
        baseline_code, baseline, baseline_wall = execute(public_tsv, len(case["queries"]), "baseline-m3", 3)
        audit_start = time.monotonic()
        for query in case["queries"]:
            audit_point = mul(curve, subset[0], int(query["audit_scalar"]))
            if [hex(audit_point.x), hex(audit_point.y)] != query["target"]:
                raise ValueError("frozen ordinary target scalar replay failed")
        def audit(raw_rows, summands):
            rank = RelationRank(int(case["subgroup_order"]), case["signed_subset"] // 2)
            for i, row in enumerate(raw_rows):
                if i >= len(case["queries"]) or [int(v, 16) for v in row["target"]] != [int(v, 16) for v in case["queries"][i]["target"]]:
                    raise ValueError("out-of-order or wrong target")
                if row["status"] != "found":
                    continue
                indices = row["witness"]
                if len(indices) != summands or any(type(v) is not int or not 0 <= v < len(subset) for v in indices):
                    raise ValueError("invalid witness indices")
                target = Point(*(int(x, 16) for x in row["target"]))
                if curve.sum(subset[j] for j in indices) != target:
                    raise ValueError("independent Python witness replay failed")
                coefficients = [0] * (len(subset) // 2)
                for j in indices:
                    coefficients[j % (len(subset) // 2)] += 1 if j < len(subset) // 2 else -1
                row["rank_status"] = rank.add(coefficients)
                row["signed_coefficients"] = coefficients
                row["verified_points"] = [[hex(subset[j].x), hex(subset[j].y)] for j in indices]
            return rank.rank
        rank5 = audit(results, 5)
        rank3 = audit(baseline, 3)
        if control_code != 0 or len(control) != 1 or control[0]["status"] != "found":
            raise ValueError("planted control was not solved")
        control_indices = control[0]["witness"]
        if curve.sum(subset[j] for j in control_indices) != Point(*(int(x, 16) for x in case["planted_control"])):
            raise ValueError("independent planted control replay failed")
        audit_seconds = time.monotonic() - audit_start
        audited = output / f"n{n}-l{l}.audited.json"
        audited.write_text(json.dumps(results, indent=2) + "\n")
        baseline_audited = output / f"n{n}-l{l}.baseline-m3.audited.json"
        baseline_audited.write_text(json.dumps(baseline, indent=2) + "\n")
        receipt = {"n": n, "l": l, "subset_B": len(subset), "full_B": case["full_signed_B"],
                   "full_pair_count": case["full_signed_B"] * (case["full_signed_B"] + 1) // 2,
                   "pair_cap": manifest["pair_entry_cap"], "status": "complete" if code == baseline_code == 0 and len(results) == len(baseline) == len(case["queries"]) else "incomplete",
                   "ordinary_statuses": {status: sum(x["status"] == status for x in results)
                                         for status in ("found", "exhausted", "budget")},
                   "independent_rank": rank5, "total_wall_seconds": wall + control_wall,
                   "ordinary_wall_seconds": wall, "control_wall_seconds": control_wall,
                   "audit_seconds": audit_seconds, "input_loading_seconds": input_loading_seconds,
                   "full_base_preparation_seconds": case["full_base_preparation_seconds"],
                   "target_generation_seconds": case["target_generation_seconds"],
                   "charged_wall_seconds": wall + audit_seconds + input_loading_seconds +
                       case["full_base_preparation_seconds"] + case["target_generation_seconds"],
                   "baseline_m3": {"status": "complete" if baseline_code == 0 and len(baseline) == len(case["queries"]) else "incomplete",
                                   "independent_rank": rank3, "ordinary_wall_seconds": baseline_wall,
                                   "statuses": {status: sum(x["status"] == status for x in baseline)
                                                for status in ("found", "exhausted", "budget")},
                                   "raw_sha256": sha(output / f"n{n}-l{l}.baseline-m3.jsonl"),
                                   "audited_sha256": sha(baseline_audited)},
                   "peak_rss_kib": max((x["peak_rss_kib"] for x in [*results, *control, *baseline]), default=None),
                   "control": control[0], "control_excluded_from_rank": True,
                   "ordinary_raw_sha256": sha(output / f"n{n}-l{l}.ordinary.jsonl"),
                   "control_raw_sha256": sha(output / f"n{n}-l{l}.control.jsonl")}
        receipt["audited_sha256"] = sha(audited)
        receipts.append(receipt)
        (output / "results.json").write_text(json.dumps({"manifest_sha256": sha(manifest_path),
                                                          "results": receipts}, indent=2) + "\n")
        print(json.dumps({"n": n, "status": receipt["status"], "statuses": receipt["ordinary_statuses"],
                          "rank_m5": rank5, "rank_m3": rank3}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="action", required=True)
    f = subs.add_parser("freeze"); f.add_argument("output", type=Path)
    r = subs.add_parser("run"); r.add_argument("manifest", type=Path); r.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "freeze": freeze(args.output)
    else: run(args.manifest, args.output)


if __name__ == "__main__":
    main()
