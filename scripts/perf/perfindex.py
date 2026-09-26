#!/usr/bin/env python3
"""Performance index: baseline vs candidate over the perfbench kernels.

    perfindex.py build   --ref REV --out DIR      # perfbench for REV, with this tree's harness
    perfindex.py build   --current --out DIR      # perfbench for the working tree
    perfindex.py compare --base BIN --cand BIN --out DIR [--rounds 5] [--threads 1]
    perfindex.py instr   --base BIN --cand BIN --out DIR   # callgrind instruction counts
    perfindex.py report  DIR/compare.json

The formula (docs/perf/PERFORMANCE_INDEX.md):

  per kernel k, round r:   d_{k,r} = ln(T_base,k,r / T_cand,k,r)      (paired, same round)
  kernel speedup:          s_k = exp(median_r d_{k,r})
  noise (A/A):             n_{k,r} = ln(T_base,k,r / T_base',k,r)     (baseline against itself)
  area index:              A_a = exp(mean_{k in a} ln s_k)
  performance index:       PI  = exp(sum_a w_a ln A_a),  sum_a w_a = 1 over areas present

A kernel whose fingerprints differ between any two runs is INVALID and the
index is refused: a faster answer to a different question is not a speedup.
Confidence intervals resample rounds jointly (rounds are paired in time).
Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

EXAMPLE = "perfbench"


def crate_dir(root: Path) -> str:
    """The Cargo crate holding the harness: the root (crypto) or suite/ (cryptanalysis)."""
    if (root / "Cargo.toml").exists():
        return "."
    if (root / "suite" / "Cargo.toml").exists():
        return "suite"
    raise SystemExit("no Cargo crate at the repository root or in suite/")


def sparse_dirs(crate: str) -> list[str]:
    """Directories a sparse build worktree checks out (cone mode keeps root files)."""
    if crate == ".":
        return ["src", "examples", "benches", "tests", "scripts", "docs"]
    return [crate, "src", "include", "tools", "cmake", "scripts", "docs"]
BOOTSTRAP = 2000


# ----------------------------------------------------------------------------
# helpers


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(out.stdout.strip())


def sha256_tree(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(path)).encode())
            h.update(b"\0")
            h.update(f.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def host_manifest() -> dict:
    def cmd(*a: str) -> str:
        try:
            return subprocess.run(a, capture_output=True, text=True).stdout.strip()
        except OSError:
            return ""

    cpu = ""
    flags: list[str] = []
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name") and not cpu:
                cpu = line.split(":", 1)[1].strip()
            if line.startswith("flags") and not flags:
                keep = re.compile(r"^(popcnt|avx2?|avx512\w*|pclmulqdq|vpclmulqdq|gfni|bmi[12]|adx)$")
                flags = [f for f in line.split(":", 1)[1].split() if keep.match(f)]
    except OSError:
        pass
    mem = ""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                mem = line.split(":", 1)[1].strip()
    except OSError:
        pass
    return {
        "cpu": cpu or platform.processor(),
        "cpu_flags": flags,
        "logical_cores": os.cpu_count(),
        "memory": mem,
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "rustc": cmd("rustc", "--version"),
        "loadavg_start": os.getloadavg() if hasattr(os, "getloadavg") else None,
    }


def run_json(cmd: list[str], env: dict, timeout: float | None = None) -> list[dict]:
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} exited {proc.returncode}:\n{proc.stderr[-4000:]}")
    return [json.loads(l) for l in proc.stdout.splitlines() if l.startswith("{")]


def list_kernels(binary: str, full: bool, filters: list[str]) -> list[dict]:
    cmd = [binary, "list"]
    if full:
        cmd.append("--full")
    ks = run_json(cmd, dict(os.environ))
    filters = [f for spec in filters for f in spec.split(",") if f]
    if filters:
        ks = [k for k in ks if any(f in k["id"] for f in filters)]
    return ks


def bootstrap_ci(values: list[float], stat, rng: random.Random, n: int = BOOTSTRAP):
    if len(values) < 2:
        v = stat(values)
        return v, v
    boots = sorted(stat([rng.choice(values) for _ in values]) for _ in range(n))
    return boots[int(0.025 * n)], boots[int(0.975 * n) - 1]


def load_weights(path: str | None) -> dict:
    if path is None:
        default = repo_root() / "docs/perf/weights.json"
        path = str(default) if default.exists() else None
    if path is None:
        return {}
    return json.loads(Path(path).read_text()).get("areas", {})


# ----------------------------------------------------------------------------
# build


def cmd_build(a: argparse.Namespace) -> None:
    root = repo_root()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    crate = crate_dir(root)
    harness_rel = Path(crate) / "examples" / EXAMPLE
    harness_src = root / harness_rel
    target = out / "target"
    env = dict(os.environ, CARGO_TARGET_DIR=str(target))
    meta = {"harness_sha256": sha256_tree(harness_src), "host": host_manifest()}
    if a.current:
        src = root
        meta["rev"] = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        meta["dirty"] = bool(
            subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain", "--", "src", "Cargo.toml"],
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    else:
        src = out / "src"
        # Sparse: the research tree is gigabytes and the build needs none of it.
        subprocess.run(
            ["git", "-C", str(root), "worktree", "add", "--no-checkout", "--detach", str(src), a.ref],
            check=True,
        )
        subprocess.run(["git", "-C", str(src), "sparse-checkout", "set", *sparse_dirs(crate)], check=True)
        subprocess.run(["git", "-C", str(src), "checkout", "--detach", a.ref], check=True)
        meta["rev"] = subprocess.run(
            ["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        # Overlay this tree's harness so both sides run identical kernels.
        dst = src / harness_rel
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(harness_src, dst)
    t0 = time.time()
    subprocess.run(
        ["cargo", "build", "--release", "--example", EXAMPLE, *a.cargo_args],
        cwd=src / crate,
        env=env,
        check=True,
    )
    meta["build_seconds"] = round(time.time() - t0, 1)
    shutil.copy2(target / "release" / "examples" / EXAMPLE, out / EXAMPLE)
    (out / "build.json").write_text(json.dumps(meta, indent=2) + "\n")
    if not a.keep:
        shutil.rmtree(target, ignore_errors=True)
        if not a.current:
            subprocess.run(["git", "-C", str(root), "worktree", "remove", "--force", str(src)])
    print(out / EXAMPLE)


# ----------------------------------------------------------------------------
# compare


def invoke(binary: str, kid: str, a: argparse.Namespace) -> dict:
    env = dict(os.environ, RAYON_NUM_THREADS=str(a.threads))
    cmd = [
        binary,
        "run",
        "--filter",
        kid,
        "--exact",
        "--samples",
        str(a.samples),
        "--max-seconds",
        str(a.max_seconds),
    ]
    if a.taskset:
        cmd = ["taskset", "-c", a.taskset] + cmd
    (row,) = run_json(cmd, env, timeout=a.timeout)
    return row


def summarize(kernels: list[dict], per: dict, weights: dict, rng: random.Random) -> dict:
    rows = []
    rounds = None
    for k in kernels:
        kid = k["id"]
        rec = per[kid]
        fps = {r["fingerprint"] for arm in ("A", "B", "A2") for r in rec.get(arm, [])}
        tA = [r["median_ns"] for r in rec["A"]]
        tB = [r["median_ns"] for r in rec["B"]]
        tA2 = [r["median_ns"] for r in rec.get("A2", [])]
        d = [math.log(x / y) for x, y in zip(tA, tB)]
        n = [math.log(x / y) for x, y in zip(tA, tA2)]
        rounds = len(d) if rounds is None else min(rounds, len(d))
        valid = len(fps) == 1
        med = statistics.median(d)
        lo, hi = bootstrap_ci(d, statistics.median, rng)
        noise = statistics.median([abs(x) for x in n]) * 1.4826 if n else None
        thresh = max(2 * noise if noise is not None else 0.0, math.log(1.02))
        if not valid:
            verdict = "INVALID"
        elif lo > 0 and med > thresh:
            verdict = "faster"
        elif hi < 0 and -med > thresh:
            verdict = "slower"
        else:
            verdict = "neutral"
        rows.append(
            {
                "id": kid,
                "area": k["area"],
                "fingerprints": sorted(fps),
                "valid": valid,
                "base_median_ns": statistics.median(tA),
                "cand_median_ns": statistics.median(tB),
                "speedup": math.exp(med),
                "speedup_ci95": [math.exp(lo), math.exp(hi)],
                "aa_noise_ln": noise,
                "verdict": verdict,
                "d": d,
                "n": n,
            }
        )
    by_area: dict[str, list[dict]] = {}
    for r in rows:
        by_area.setdefault(r["area"], []).append(r)
    areas = sorted(by_area)
    w = {ar: float(weights.get(ar, 1.0)) for ar in areas}
    wsum = sum(w.values()) or 1.0
    w = {ar: v / wsum for ar, v in w.items()}

    def index_for(rounds_idx: list[int]) -> tuple[float, dict]:
        area_ln = {}
        for ar in areas:
            lns = []
            for r in by_area[ar]:
                ds = [r["d"][i] for i in rounds_idx if i < len(r["d"])]
                lns.append(statistics.median(ds))
            area_ln[ar] = sum(lns) / len(lns)
        return sum(w[ar] * area_ln[ar] for ar in areas), area_ln

    all_idx = list(range(rounds or 0))
    pi_ln, area_ln = index_for(all_idx)
    boots = []
    for _ in range(BOOTSTRAP if rounds and rounds > 1 else 0):
        idx = [rng.randrange(rounds) for _ in range(rounds)]
        boots.append(index_for(idx)[0])
    boots.sort()
    ci = (
        [math.exp(boots[int(0.025 * len(boots))]), math.exp(boots[int(0.975 * len(boots)) - 1])]
        if boots
        else [math.exp(pi_ln)] * 2
    )
    valid = all(r["valid"] for r in rows)
    return {
        "valid": valid,
        "performance_index": math.exp(pi_ln) if valid else None,
        "performance_index_ci95": ci if valid else None,
        "areas": {
            ar: {"index": math.exp(area_ln[ar]), "weight": w[ar], "kernels": len(by_area[ar])}
            for ar in areas
        },
        "kernels": rows,
        "rounds": rounds,
    }


def markdown(summary: dict, title: str) -> str:
    out = [f"# {title}", ""]
    if summary["valid"]:
        lo, hi = summary["performance_index_ci95"]
        out.append(
            f"**Performance index PI = {summary['performance_index']:.3f}x** "
            f"(95% CI {lo:.3f}–{hi:.3f}, {summary['rounds']} paired rounds)"
        )
    else:
        out.append("**INVALID: at least one kernel's output fingerprint changed. No index.**")
    out += ["", "| area | weight | kernels | area index |", "|:--|--:|--:|--:|"]
    for ar, v in summary["areas"].items():
        out.append(f"| {ar} | {v['weight']:.3f} | {v['kernels']} | {v['index']:.3f}x |")
    unit = summary.get("unit", "ms")
    out += [
        "",
        f"| kernel | base {unit} | cand {unit} | speedup | 95% CI | A/A noise | verdict |",
        "|:--|--:|--:|--:|:--|--:|:--|",
    ]
    scale = 1e6 if unit == "ms" else 1.0
    for r in summary["kernels"]:
        lo, hi = r["speedup_ci95"]
        noise = r.get("aa_noise_ln")
        noise_s = f"±{100 * (math.exp(noise) - 1):.1f}%" if noise is not None else "n/a"
        out.append(
            f"| `{r['id']}` | {r['base_median_ns'] / scale:.3f} | {r['cand_median_ns'] / scale:.3f} "
            f"| {r['speedup']:.3f}x | {lo:.3f}–{hi:.3f} | {noise_s} | {r['verdict']} |"
        )
    return "\n".join(out) + "\n"


def cmd_compare(a: argparse.Namespace) -> None:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    rng = random.Random(a.seed)
    kb = {k["id"]: k for k in list_kernels(a.base, a.full, a.filter)}
    kc = {k["id"]: k for k in list_kernels(a.cand, a.full, a.filter)}
    only = sorted(set(kb) ^ set(kc))
    if only:
        print(f"kernels present on one side only (skipped): {only}", file=sys.stderr)
    kernels = [kc[i] for i in sorted(set(kb) & set(kc))]
    per: dict[str, dict] = {k["id"]: {"A": [], "B": [], "A2": []} for k in kernels}
    host = host_manifest()
    for r in range(a.rounds):
        order = kernels[:]
        rng.shuffle(order)
        for k in order:
            arms = ["A", "B", "A2"] if a.aa else ["A", "B"]
            rot = r % len(arms)
            arms = arms[rot:] + arms[:rot]
            for arm in arms:
                binary = a.cand if arm == "B" else a.base
                row = invoke(binary, k["id"], a)
                row["round"] = r
                per[k["id"]][arm].append(row)
            print(
                f"round {r + 1}/{a.rounds} {k['id']}: "
                + " ".join(f"{arm}={per[k['id']][arm][-1]['median_ns'] / 1e6:.3f}ms" for arm in arms),
                file=sys.stderr,
            )
    host["loadavg_end"] = os.getloadavg() if hasattr(os, "getloadavg") else None
    summary = summarize(kernels, per, load_weights(a.weights), rng)
    summary.update(
        {
            "mode": "wall",
            "unit": "ms",
            "base": a.base,
            "cand": a.cand,
            "threads": a.threads,
            "samples_per_invocation": a.samples,
            "host": host,
            "raw": per,
        }
    )
    (out / "compare.json").write_text(json.dumps(summary, indent=1) + "\n")
    (out / "compare.md").write_text(markdown(summary, "perfbench wall-time comparison"))
    print(markdown(summary, "perfbench wall-time comparison"))
    if not summary["valid"]:
        sys.exit(1)


# ----------------------------------------------------------------------------
# instr (callgrind)

COLLECTED = re.compile(r"Collected\s*:\s*(\d+)")


def instr_one(binary: str, kid: str) -> dict:
    env = dict(os.environ, RAYON_NUM_THREADS="1")
    cmd = [
        "valgrind",
        "--tool=callgrind",
        "--callgrind-out-file=/dev/null",
        "--collect-atstart=no",
        "--toggle-collect=*perfbench_measured_region*",
        binary,
        "run",
        "--filter",
        kid,
        "--exact",
        "--instr",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"callgrind failed for {kid}:\n{proc.stderr[-3000:]}")
    m = COLLECTED.search(proc.stderr)
    (row,) = [json.loads(l) for l in proc.stdout.splitlines() if l.startswith("{")]
    row["ir"] = int(m.group(1)) if m else None
    return row


def cmd_instr(a: argparse.Namespace) -> None:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    kb = {k["id"]: k for k in list_kernels(a.base, a.full, a.filter)}
    kc = {k["id"]: k for k in list_kernels(a.cand, a.full, a.filter)}
    kernels = [kc[i] for i in sorted(set(kb) & set(kc))]
    per = {}
    for k in kernels:
        ra = instr_one(a.base, k["id"])
        rb = instr_one(a.cand, k["id"])
        # One deterministic measurement a side: express it in the compare format.
        per[k["id"]] = {
            "A": [{"median_ns": ra["ir"], "fingerprint": ra["fingerprint"]}],
            "B": [{"median_ns": rb["ir"], "fingerprint": rb["fingerprint"]}],
        }
        print(f"{k['id']}: base Ir={ra['ir']} cand Ir={rb['ir']}", file=sys.stderr)
    summary = summarize(kernels, per, load_weights(a.weights), random.Random(0))
    summary.update({"mode": "callgrind_ir", "unit": "Ir", "base": a.base, "cand": a.cand})
    (out / "instr.json").write_text(json.dumps(summary, indent=1) + "\n")
    md = markdown(summary, "perfbench instruction-count comparison (callgrind Ir, 1 thread)")
    (out / "instr.md").write_text(md)
    print(md)
    if not summary["valid"]:
        sys.exit(1)


def cmd_report(a: argparse.Namespace) -> None:
    s = json.loads(Path(a.json).read_text())
    print(markdown(s, "perfbench comparison"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build perfbench for a revision with this tree's harness")
    g = b.add_mutually_exclusive_group(required=True)
    g.add_argument("--ref")
    g.add_argument("--current", action="store_true")
    b.add_argument("--out", required=True)
    b.add_argument("--keep", action="store_true", help="keep the worktree and target dir")
    b.add_argument("cargo_args", nargs="*")
    b.set_defaults(func=cmd_build)

    for name, func in (("compare", cmd_compare), ("instr", cmd_instr)):
        c = sub.add_parser(name)
        c.add_argument("--base", required=True)
        c.add_argument("--cand", required=True)
        c.add_argument("--out", required=True)
        c.add_argument("--filter", action="append", default=[])
        c.add_argument("--full", action="store_true")
        c.add_argument("--weights")
        if name == "compare":
            c.add_argument("--rounds", type=int, default=5)
            c.add_argument("--threads", type=int, default=1)
            c.add_argument("--samples", type=int, default=5)
            c.add_argument("--max-seconds", type=float, default=2.0)
            c.add_argument("--timeout", type=float, default=900)
            c.add_argument("--taskset", help="CPU list for taskset, e.g. 2")
            c.add_argument("--no-aa", dest="aa", action="store_false")
            c.add_argument("--seed", type=int, default=20260926)
        c.set_defaults(func=func)

    r = sub.add_parser("report")
    r.add_argument("json")
    r.set_defaults(func=cmd_report)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
