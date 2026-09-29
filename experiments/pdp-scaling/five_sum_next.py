#!/usr/bin/env python3
"""Frozen paired five-sum development trials; no full-DLP claim.

Freeze writes natural subgroup targets before either solver runs. The direct
point solver is a control and a feasibility screen, not an S6 solver.
"""

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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from gf2n import Curve, GF2n, INF, Point
from groebner_compare.relation_metrics import RelationRank
from target_fiber import scalar_mul

NATIVE = HERE / "five_sum_mitm.cpp"
ARCHIVE = HERE / "explicit-base-frontier-20260928/run-2/n83-l17.jsonl.xz"
N83_EVIDENCE = HERE / "ordinary-evidence-20260928/n83.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(p):
    return [hex(p.x), hex(p.y)]


def restored(row):
    return Point(int(row[0], 16), int(row[1], 16))


def base31(l):
    field = GF2n(31)
    curve = Curve(field, 1)
    r, h = 1439393, 1492
    # Trial division is a complete primality check at this development size.
    if any(r % d == 0 for d in range(2, int(r**0.5) + 1)):
        raise ValueError("n31 subgroup order is not prime")
    if 4 * 373 * r != 2147574356:
        raise ValueError("unexpected curve order")
    originals = sorted({q for x in range(1 << l) if (p := curve.lift_x(x)) is not None
                        for q in (p, curve.neg(p))}, key=lambda p: (p.x, p.y))
    projected = {scalar_mul(curve, p, h) for p in originals} - {INF}
    reps = sorted({min((p, curve.neg(p)), key=lambda q: (q.x, q.y)) for p in projected},
                  key=lambda p: (p.x, p.y))
    if not reps or len(projected) != 2 * len(reps) or any(scalar_mul(curve, p, r) != INF for p in reps):
        raise ValueError("invalid subgroup base")
    return curve, {"n": 31, "l": l, "modulus": field.mod, "r": r, "cofactor": h,
                   "original_points": list(map(encoded, originals)),
                   "representatives": list(map(encoded, reps)), "B": 2 * len(reps),
                   "columns": len(reps), "construction": "all x<2^l; both signs; [1492] projection"}


def base83():
    record = json.loads(N83_EVIDENCE.read_text())["base"]
    field = GF2n(83, record["modulus"])
    curve = Curve(field, 1)
    lines = lzma.decompress(ARCHIVE.read_bytes()).splitlines()
    summary = json.loads(lines[-1])
    if summary.get("summary") is not True:
        raise ValueError("incomplete archived base")
    reps = sorted({(int(q["projected_x"], 16), int(q["projected_y"], 16))
                   for line in lines[:-1] for q in [json.loads(line)]})
    if len(reps) * 2 != summary["signed_projected_B"] or len(reps) != 65302:
        raise ValueError("archived count mismatch")
    return curve, {"n": 83, "l": 17, "modulus": field.mod,
                   "r": record["subgroup_order"], "cofactor": 4,
                   "archive": str(ARCHIVE.relative_to(ROOT)), "archive_sha256": digest(ARCHIVE),
                   "representatives": [[hex(x), hex(y)] for x, y in reps],
                   "B": len(reps) * 2, "columns": len(reps),
                   "construction": "audited full x<2^17 base; [4] projection"}


def freeze(path, n, l, seeds, attempts):
    start = time.monotonic()
    curve, base = base31(l) if n == 31 else base83()
    base_seconds = time.monotonic() - start
    generator = restored(base["representatives"][0])
    if scalar_mul(curve, generator, base["r"]) != INF:
        raise ValueError("generator not in subgroup")
    streams = []
    for seed in seeds:
        begin = time.monotonic()
        rng = random.Random(seed)
        queries = []
        for _ in range(attempts):
            k = rng.randrange(1, base["r"])
            queries.append({"target": encoded(scalar_mul(curve, generator, k)), "audit_scalar": str(k)})
        streams.append({"seed": seed, "queries": queries,
                        "target_generation_seconds": time.monotonic() - begin})
    manifest = {"schema": "five-sum-next-v1", "scope": "PDP stage only", "candidate_id": None,
                "base": base, "base_construction_seconds": base_seconds,
                "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in
                                  (Path(__file__), NATIVE, HERE / "target_fiber.py")},
                "streams": streams, "query_law": "uniform nonzero scalar in prime subgroup",
                "rank_goal": 8, "memory_mib": 512, "seconds_per_target": 5,
                "max_triples_per_target": 50000, "pair_entry_cap": 1500000,
                "arms": ["direct-m3", "direct-m5"],
                "claim_rule": "paired five seeds and rank eight in both arms; include all failed queries and construction"}
    with path.open("x") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(json.dumps({"manifest": str(path), "sha256": digest(path), "B": base["B"],
                      "columns": base["columns"]}))


def run(path, output):
    manifest = json.loads(path.read_text())
    for name, expected in manifest["source_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"changed frozen source: {name}")
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_bytes(path.read_bytes())
    base = manifest["base"]
    curve = Curve(GF2n(base["n"], base["modulus"]), 1)
    reps = list(map(restored, base["representatives"]))
    points = reps + [curve.neg(p) for p in reps]
    if len(set(points)) != base["B"] or any(not curve.on_curve(p) for p in points):
        raise ValueError("invalid point base")
    setup_start = time.monotonic()
    base_path = output / "base.tsv"
    base_path.write_text("".join(f"{p.x:x} {p.y:x}\n" for p in points))
    pair_count = base["B"] * (base["B"] + 1) // 2
    results = {"manifest_sha256": digest(path), "host": platform.platform(),
               "pair_entries": pair_count, "streams": []}
    if pair_count <= manifest["pair_entry_cap"]:
        subprocess.run(["g++", "-O3", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(NATIVE),
                        "-o", str(output / "solver")], check=True, capture_output=True, timeout=60)
        results["solver_sha256"] = digest(output / "solver")
    else:
        results["solver_sha256"] = None
    setup_seconds = time.monotonic() - setup_start
    for stream in manifest["streams"]:
        input_start = time.monotonic()
        seed = stream["seed"]
        targets = [restored(q["target"]) for q in stream["queries"]]
        if any(scalar_mul(curve, points[0], int(q["audit_scalar"])) != target
               for target, q in zip(targets, stream["queries"])):
            raise ValueError("target scalar replay failed")
        targets_path = output / f"seed-{seed}.targets.tsv"
        targets_path.write_text("".join(f"{p.x:x} {p.y:x}\n" for p in targets))
        input_seconds = time.monotonic() - input_start
        shared_seconds = manifest["base_construction_seconds"] / len(manifest["streams"]) \
            + stream["target_generation_seconds"] + setup_seconds / len(manifest["streams"]) \
            + input_seconds
        arms = {}
        for name, m in (("direct-m3", 3), ("direct-m5", 5)):
            if results["solver_sha256"] is None:
                arms[name] = {"status": "pair-cap", "found": 0, "rank": 0,
                              "attempted": 0, "charged_seconds": shared_seconds,
                              "reason": f"{pair_count} entries exceed {manifest['pair_entry_cap']} cap"}
                continue
            arm_start = time.monotonic()
            rank = RelationRank(base["r"], len(reps))
            raw_path = output / f"seed-{seed}.{name}.jsonl"
            def cap():
                limit = manifest["memory_mib"] * 1024**2
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            cmd = [str(output / "solver"), str(base["n"]), str(base["modulus"]),
                   str(base_path), str(targets_path), str(manifest["max_triples_per_target"]),
                   str(manifest["seconds_per_target"]), str(len(targets)), str(m)]
            begin = time.monotonic()
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, preexec_fn=cap,
                                      timeout=len(targets) * (manifest["seconds_per_target"] + 2) + 20)
                raw_path.write_text(proc.stdout)
                code, error = proc.returncode, proc.stderr
            except subprocess.TimeoutExpired as exc:
                raw_path.write_bytes(exc.stdout or b"")
                code, error = None, "external watchdog timeout"
            wall = time.monotonic() - begin
            rows = [json.loads(line) for line in raw_path.read_text().splitlines()]
            statuses = {s: 0 for s in ("found", "budget", "exhausted")}
            audited = []
            for i, row in enumerate(rows):
                if i >= len(targets) or restored(row["target"]) != targets[i]:
                    raise ValueError("out-of-order target")
                statuses[row["status"]] += 1
                if row["status"] == "found":
                    indices = row["witness"]
                    if len(indices) != m or any(type(j) is not int or not 0 <= j < len(points) for j in indices):
                        raise ValueError("bad witness")
                    if curve.sum(points[j] for j in indices) != targets[i]:
                        raise ValueError("exact independent witness replay failed")
                    coefficients = [0] * len(reps)
                    for j in indices:
                        coefficients[j % len(reps)] += 1 if j < len(reps) else -1
                    row["rank_status"] = rank.add(coefficients)
                    row["coefficients"] = coefficients
                    row["projected_replay"] = True
                audited.append(row)
            (output / f"seed-{seed}.{name}.audited.json").write_text(json.dumps(audited) + "\n")
            arms[name] = {"status": "complete" if code == 0 and len(rows) == len(targets) else "incomplete",
                          "exit_code": code, "stderr": error, "attempted": len(rows),
                          "statuses": statuses, "rank": rank.rank, "wall_seconds": wall,
                          "charged_seconds": time.monotonic() - arm_start + shared_seconds,
                          "peak_rss_kib": max((row["peak_rss_kib"] for row in rows), default=None),
                          "raw_sha256": digest(raw_path)}
        results["streams"].append({"seed": seed, "arms": arms})
        (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps({"seed": seed, "arms": {k: {"status": v["status"], "rank": v["rank"]}
                                                 for k, v in arms.items()}}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("output", type=Path)
    f.add_argument("--n", type=int, choices=(31, 83), required=True)
    f.add_argument("--l", type=int, default=6)
    f.add_argument("--seeds", type=int, nargs="+", default=list(range(210031, 210036)))
    f.add_argument("--attempts", type=int, default=24)
    r = sub.add_parser("run")
    r.add_argument("manifest", type=Path)
    r.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "freeze":
        freeze(args.output, args.n, args.l, args.seeds, args.attempts)
    else:
        run(args.manifest, args.output)
