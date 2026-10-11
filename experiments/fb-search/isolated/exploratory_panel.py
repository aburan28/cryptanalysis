#!/usr/bin/env python3
"""Run an isolated_bench.py manifest directly, without isolation, as an exploratory check.

This exercises the same argv, output protocol and pairing rules as scripts/isolated_bench.py (alternating
reference/candidate order, verified=1 and online_ms required, pair_fields must match), but performs no
preflight, CPU pinning or noise gating.  Its output is labelled `"controlled": false` and must not be
cited as a CPU speedup (AGENTS.md, CPU performance isolation gate).

    python3 exploratory_panel.py MANIFEST.json --out results/ic-rho-exploratory.jsonl [--cases 0-31,64-75]
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import random
import statistics
import subprocess
import time
from pathlib import Path


def fields(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        f = dict(w.split("=", 1) for w in line.split() if "=" in w)
        if "online_ms" in f:
            return f
    return {}


def parse_ranges(text: str) -> list[int]:
    out = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", default="")
    ap.add_argument("--summarize", action="store_true", help="only summarize --out")
    args = ap.parse_args()
    if args.summarize:
        print(json.dumps(summarize(args.out), indent=1, sort_keys=True))
        return
    m = json.loads(args.manifest.read_text())
    cases = m["cases"]
    if args.cases:
        cases = [cases[i] for i in parse_ranges(args.cases)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as fh:
        for index, case in enumerate(cases):
            order = ("reference", "candidate") if index % 2 == 0 else ("candidate", "reference")
            pair = {}
            for variant in order:
                t0 = time.monotonic_ns()
                p = subprocess.run(case[variant], cwd=m["workdir"], capture_output=True, text=True,
                                   timeout=m["timeout_s"])
                f = fields(p.stdout)
                ok = p.returncode == 0 and f.get("verified") == "1"
                try:
                    ms = float(f["online_ms"])
                    ok = ok and math.isfinite(ms) and ms > 0
                except (KeyError, ValueError):
                    ms, ok = None, False
                pair[variant] = {"valid": ok, "online_ms": ms, "fields": f, "returncode": p.returncode,
                                 "outer_ms": (time.monotonic_ns() - t0) / 1e6, "stderr_tail": p.stderr[-500:]}
            issues = [v for v, r in pair.items() if not r["valid"]]
            if not issues:
                bad = [k for k in m["pair_fields"]
                       if not pair["reference"]["fields"].get(k)
                       or pair["reference"]["fields"][k] != pair["candidate"]["fields"].get(k)]
                if bad:
                    issues.append("pair mismatch: " + ",".join(bad))
            rec = {"schema": "ic-rho-exploratory/1", "controlled": False, "manifest": m["name"], "case": case["id"],
                   "host": platform.node(), "order": list(order), "status": "valid" if not issues else "invalid",
                   "issues": issues, "reference": pair["reference"], "candidate": pair["candidate"],
                   "online_speedup": (pair["reference"]["online_ms"] / pair["candidate"]["online_ms"])
                   if not issues else None}
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
            print(f"{case['id']:16s} {rec['status']:7s} rho={pair['reference']['online_ms']} "
                  f"ic={pair['candidate']['online_ms']} speedup={rec['online_speedup']}", flush=True)


def summarize(path: Path) -> dict:
    """Per panel group (case-id prefix, e.g. n19): valid pairs, invalid rows, and the paired geometric-mean
    online speedup rho/IC with a bootstrap 95% interval."""
    rows = [json.loads(line) for line in path.open() if line.strip()]
    out = {}
    for group in sorted({r["case"].split("-")[0] for r in rows}):
        g = [r for r in rows if r["case"].split("-")[0] == group]
        ok = [r for r in g if r["status"] == "valid"]
        if not ok:
            out[group] = {"valid_pairs": 0, "invalid": len(g)}
            continue
        logs = [math.log(r["online_speedup"]) for r in ok]
        rng = random.Random(group)
        boot = sorted(statistics.fmean(rng.choices(logs, k=len(logs))) for _ in range(4000))
        ic = [r["candidate"]["online_ms"] for r in ok]
        rho = [r["reference"]["online_ms"] for r in ok]
        out[group] = {"curve_id": ok[0]["reference"]["fields"]["curve_id"],
                      "candidate_id": ok[0]["candidate"]["fields"].get("candidate_id"),
                      "valid_pairs": len(ok), "invalid": len(g) - len(ok),
                      "geomean_speedup": math.exp(statistics.fmean(logs)),
                      "speedup_ci95": [math.exp(boot[100]), math.exp(boot[3899])],
                      "ic_faster_pairs": sum(1 for r in ok if r["online_speedup"] > 1),
                      "median_ic_ms": statistics.median(ic), "median_rho_ms": statistics.median(rho),
                      "mean_ic_ms": statistics.fmean(ic), "mean_rho_ms": statistics.fmean(rho),
                      "controlled": False}
    return out


if __name__ == "__main__":
    main()
