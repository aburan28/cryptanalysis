"""Run a grid of PDP instances through one engine and append the results to a CSV.

    python3 run.py --engine sat --m 3 --ns 17,31,61 --ls 3,4,5,6 --seeds 3 --timeout 600 --out results/sat.csv

Each (n, l, seed) is one subprocess with a hard wall-clock limit; a timeout
is recorded as such.  For a given n the l sweep stops after the first
timeout, since larger l only gets worse.  Rows already in the CSV are
skipped, so an interrupted run resumes.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

FIELDS = [
    "engine",
    "curve",
    "m",
    "n",
    "l",
    "seed",
    "threads",
    "vars",
    "monomials",
    "build_seconds",
    "status",
    "seconds",
    "verified",
    "detail",
]


def done_keys(path: Path) -> dict[tuple, str]:
    if not path.exists():
        return {}
    with path.open() as fh:
        return {
            (
                r["engine"],
                r["curve"],
                int(r["m"]),
                int(r["n"]),
                int(r["l"]),
                int(r["seed"]),
            ): r["status"]
            for r in csv.DictReader(fh)
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--m", type=int, required=True)
    ap.add_argument("--ns", required=True, help="comma-separated field degrees")
    ap.add_argument(
        "--ls", required=True, help="comma-separated factor-base dimensions"
    )
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--random-curve", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen = done_keys(out)
    new_file = not out.exists()
    curve = "random" if a.random_curve else "koblitz"
    here = Path(__file__).parent

    with out.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for n in (int(x) for x in a.ns.split(",")):
            for l in (int(x) for x in a.ls.split(",")):
                if l > n:
                    continue
                timed_out = False
                for seed in range(1, a.seeds + 1):
                    key = (a.engine, curve, a.m, n, l, seed)
                    if key in seen:
                        if seen[key] in ("timeout", "error"):
                            timed_out = True
                        continue
                    cmd = [
                        sys.executable,
                        str(here / "solve.py"),
                        "--engine",
                        a.engine,
                        "--n",
                        str(n),
                        "--m",
                        str(a.m),
                        "--l",
                        str(l),
                        "--seed",
                        str(seed),
                        "--timeout",
                        str(a.timeout),
                        "--threads",
                        str(a.threads),
                    ]
                    if a.random_curve:
                        cmd.append("--random-curve")
                    try:
                        r = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=a.timeout + 300,
                            check=False,
                        )
                        res = (
                            json.loads(r.stdout.strip().splitlines()[-1])
                            if r.returncode == 0
                            else {
                                "status": "error",
                                "seconds": "",
                                "detail": r.stderr[-300:].replace("\n", " "),
                            }
                        )
                    except subprocess.TimeoutExpired:
                        res = {"status": "timeout", "seconds": a.timeout}
                    except (json.JSONDecodeError, IndexError):
                        res = {
                            "status": "error",
                            "seconds": "",
                            "detail": (r.stderr or r.stdout)[-300:].replace("\n", " "),
                        }
                    detail = {
                        k: res[k]
                        for k in (
                            "aux_vars",
                            "input_bytes",
                            "group_ops",
                            "basis_size",
                            "free_vars",
                            "is_planted",
                            "conflicts",
                            "model_vars",
                            "model_monomials",
                        )
                        if k in res
                    }
                    row = {
                        "engine": a.engine,
                        "curve": curve,
                        "m": a.m,
                        "n": n,
                        "l": l,
                        "seed": seed,
                        "threads": a.threads,
                        "vars": res.get("vars", a.m * l),
                        "monomials": res.get("monomials", ""),
                        "build_seconds": f"{res['build_seconds']:.3f}"
                        if "build_seconds" in res
                        else "",
                        "status": res["status"],
                        "seconds": f"{res['seconds']:.4f}"
                        if isinstance(res.get("seconds"), (int, float))
                        else res.get("seconds", ""),
                        "verified": res.get("verified", ""),
                        "detail": res.get(
                            "detail", json.dumps(detail, separators=(",", ":"))
                        ),
                    }
                    w.writerow(row)
                    fh.flush()
                    print(
                        f"{a.engine} m={a.m} n={n} l={l} seed={seed}: {row['status']} {row['seconds']}s",
                        flush=True,
                    )
                    if row["status"] in ("timeout", "error"):
                        timed_out = True
                if timed_out:
                    break


if __name__ == "__main__":
    main()
