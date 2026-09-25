#!/usr/bin/env python3
"""Run the F4 GPU benchmark matrix on this host and write its receipts.

    python3 experiments/f4-gpu-20260925/gpu_bench.py --out /tmp/f4-gpu
    python3 experiments/f4-gpu-20260925/gpu_bench.py --out /tmp/f4-cpu --skip-cuda

Expects the release binaries of `suite/` built with

    cargo build --release --features gpu-emulator --bin ca-ic \
        --example f4_batch_bench --example groebner_stage_bench

and, for the CUDA backend, an NVIDIA driver plus NVRTC (`CA_NVRTC_LIB` names
the library when it is not on the loader path).  `run_modal.sh` runs exactly
this on a Modal GPU through `cloud/modal_run.py`.

What it runs, every step checked:

1. `groebner_stage_bench` on one thread: the frozen ladder's verdict digests
   must equal the committed receipts', which ties this host's kernel to the
   measured one and calibrates its single-thread speed.
2. `f4_batch_bench` on each degree-23 curve with `rayon`, `lockstep:cpu` and
   `lockstep:cuda`: every verdict digest must agree (the bench aborts
   otherwise), then the recorded Macaulay requests are replayed through the
   host kernel on one thread, on every core, and on the GPU, each answer
   checked against the host kernel's.
3. Complete `ca-ic run --solver groebner` DLPs on `K_1/2^23` at each batch
   size, on the cores and with `--f4-backend cpu|cuda`: at one batch size all
   must recover the same verified logarithm with the same trials, relations
   and reductions.

A step that fails is recorded, never skipped silently; the exit status is
nonzero when any check fails.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd: list[str], log: Path, env: dict | None = None, timeout: int = 7200) -> dict:
    """Run `cmd`, keep its output in `log`, and return its status and wall."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, **(env or {})})
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        code = "timeout"
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
    wall = time.monotonic() - t0
    log.write_text(f"$ {' '.join(cmd)}\n# exit {code}, {wall:.3f} s\n{out}\n--- stderr ---\n{err}")
    return {"cmd": cmd, "exit": code, "wall_seconds": wall, "stdout": out, "log": log.name}


def host_info() -> dict:
    def sh(cmd: str) -> str:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""

    def read(path: str) -> str:
        try:
            return Path(path).read_text().strip()
        except OSError:
            return ""
    # A container may see every host CPU yet be held to a quota; rayon
    # sizes its pool from the quota, so both are recorded.
    return {
        "hostname": platform.node(),
        "cpus": os.cpu_count(),
        "cpus_schedulable": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "cgroup_cpu_max": read("/sys/fs/cgroup/cpu.max"),
        "rayon_num_threads_env": os.environ.get("RAYON_NUM_THREADS"),
        "omp_num_threads_env": os.environ.get("OMP_NUM_THREADS"),
        "cpu_model": sh("grep -m1 'model name' /proc/cpuinfo | cut -d: -f2").strip(),
        "memory_kb": sh("grep MemTotal /proc/meminfo | awk '{print $2}'"),
        "gpus": sh("nvidia-smi --query-gpu=name,compute_cap,memory.total,driver_version "
                   "--format=csv,noheader"),
        "kernel": platform.release(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--suite", type=Path, default=HERE.parent.parent / "suite")
    ap.add_argument("--target-dir", type=Path, default=None,
                    help="cargo target directory (default SUITE/target)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--targets", type=int, default=1024)
    ap.add_argument("--replay-cap", type=int, default=200_000)
    ap.add_argument("--replay-batch", type=int, default=16_384)
    ap.add_argument("--batches", default="64,1024")
    ap.add_argument("--skip-cuda", action="store_true")
    args = ap.parse_args()

    target = args.target_dir or Path(os.environ.get("CARGO_TARGET_DIR", args.suite / "target"))
    ic = target / "release" / "ca-ic"
    batch_bench = target / "release" / "examples" / "f4_batch_bench"
    stage_bench = target / "release" / "examples" / "groebner_stage_bench"
    for binary in (ic, batch_bench, stage_bench):
        if not binary.exists():
            print(f"missing {binary}; build it first (see the module docstring)", file=sys.stderr)
            return 2
    out = args.out
    if out.exists():
        print(f"{out} exists; use a new directory", file=sys.stderr)
        return 2
    (out / "logs").mkdir(parents=True)
    summary: dict = {"host": host_info(), "started_unix": time.time(), "checks": [], "steps": {}}
    cuda = not args.skip_cuda
    failures = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        summary["checks"].append({"check": name, "ok": ok, "detail": detail})
        failures += 0 if ok else 1
        print(f"[{'ok' if ok else 'FAIL'}] {name} {detail}", flush=True)

    # 1. Frozen ladder, one thread: same verdicts as the committed receipts.
    stage_dir = out / "stage"
    r = run([str(stage_bench), "--label", "gpu-host", "--out", str(stage_dir)],
            out / "logs" / "stage.txt")
    summary["steps"]["stage"] = {k: v for k, v in r.items() if k != "stdout"}
    committed = json.loads((HERE / "receipts/stage/fast-rep1/stage.json").read_text())["rows"]
    if r["exit"] == 0:
        rows = json.loads((stage_dir / "stage.json").read_text())["rows"]
        same = [a["verdict_digest"] == b["verdict_digest"] and a["reductions"] == b["reductions"]
                for a, b in zip(rows, committed)]
        check("stage ladder verdicts equal the committed receipts", all(same) and len(same) == 6)
        summary["steps"]["stage"]["wall_seconds_by_rung"] = {
            f"{row['curve']} m={row['m']}": row["wall_ns"] / 1e9 for row in rows}
    else:
        check("stage ladder ran", False, f"exit {r['exit']}")

    # 2. Batched decisions: modes agree, replay throughput per backend.
    modes = "rayon,lockstep:cpu" + (",lockstep:cuda" if cuda else "")
    summary["steps"]["batch"] = {}
    for a in (1, 0):
        name = f"k{a}-n23"
        r = run([str(batch_bench), "--degree", "23", "--curve-a", str(a), "--targets",
                 str(args.targets), "--modes", modes, "--replay-cap", str(args.replay_cap),
                 "--replay-batch", str(args.replay_batch), "--out", str(out / "batch" / name)],
                out / "logs" / f"batch-{name}.txt")
        summary["steps"]["batch"][name] = {k: v for k, v in r.items() if k != "stdout"}
        skipped = "skipped" in r["stdout"]
        check(f"f4_batch_bench {name}: every mode decided identically, every replayed "
              "decision matched the host kernel", r["exit"] == 0 and not skipped,
              f"exit {r['exit']}{', a backend was skipped' if skipped else ''}")
        if r["exit"] == 0:
            doc = json.loads((out / "batch" / name / "f4_batch.json").read_text())
            summary["steps"]["batch"][name]["rayon_threads"] = doc["threads"]
            summary["steps"]["batch"][name]["modes"] = {
                m["mode"]: {"wall_seconds": m["wall_seconds"], "rounds": m["lockstep_rounds"],
                            "requests": m["lockstep_requests"], "decider": m["decider"],
                            "setup_seconds": m["setup_seconds"]} for m in doc["modes"]}
            summary["steps"]["batch"][name]["replay"] = {
                b["backend"]: {"decisions_per_second": b["decisions_per_second"],
                               "decider": b["decider"], "setup_seconds": b["setup_seconds"]}
                for b in doc["replay"]["backends"]}

    # 3. Complete DLPs at each batch size, on the cores and on each backend.
    summary["steps"]["e2e"] = {}
    backends = [None, "cpu"] + (["cuda"] if cuda else [])
    for batch in [int(b) for b in args.batches.split(",") if b]:
        reports = {}
        for backend in backends:
            label = f"batch{batch}-{backend or 'cores'}"
            cmd = [str(ic), "run", "--degree", "23", "--curve-a", "1", "--solver", "groebner",
                   "--batch", str(batch), "--json"]
            if backend:
                cmd += ["--f4-backend", backend]
            r = run(cmd, out / "logs" / f"e2e-{label}.txt")
            (out / "e2e").mkdir(exist_ok=True)
            (out / "e2e" / f"{label}.json").write_text(r["stdout"])
            try:
                rep = json.loads(r["stdout"])
            except json.JSONDecodeError:
                check(f"e2e {label} produced a report", False, f"exit {r['exit']}")
                continue
            reports[label] = rep
            summary["steps"]["e2e"][label] = {
                "exit": r["exit"], "status": rep.get("status"),
                "verified": rep.get("result", {}).get("verified"),
                "recovered": rep.get("result", {}).get("recovered"),
                "trials": rep.get("counts", {}).get("trials"),
                "relations": rep.get("counts", {}).get("relations"),
                "f4_reductions": rep.get("counts", {}).get("f4_reductions"),
                "relation_collection_seconds": rep.get("timing_seconds", {}).get("relation_collection"),
                "process_wall_seconds": r["wall_seconds"],
                "process_cpu_seconds": rep.get("resources", {}).get("cpu_seconds"),
                "f4_batch": rep.get("f4_batch"),
            }
        keys = ("trials", "relations", "f4_reductions", "recovered")
        rows = [summary["steps"]["e2e"][label] for label in reports]
        agree = bool(rows) and all(all(row[k] == rows[0][k] for k in keys) for row in rows)
        check(f"e2e batch {batch}: every backend verified the same logarithm with the same "
              "trials, relations and reductions",
              agree and all(row["verified"] is True for row in rows) and len(rows) == len(backends))

    summary["finished_unix"] = time.time()
    summary["failures"] = failures
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    print("\n== summary ==")
    print(json.dumps(summary["host"], indent=2))
    for name, step in summary["steps"].get("batch", {}).items():
        for backend, b in step.get("replay", {}).items():
            print(f"replay {name} {backend:>14}: {b['decisions_per_second']:12.0f} decisions/s"
                  f"  (setup {b['setup_seconds']:.3f} s, {b['decider'] or 'host kernel'})")
        for mode, m in step.get("modes", {}).items():
            print(f"modes  {name} {mode:>14}: {m['wall_seconds']:8.3f} s"
                  f"  (setup {m['setup_seconds']:.3f} s)")
    for label, row in summary["steps"].get("e2e", {}).items():
        print(f"e2e    {label:>18}: collection {row['relation_collection_seconds']} s, "
              f"verified {row['verified']}, log {row['recovered']}")
    print(f"\n{failures} check(s) failed; receipts in {out}")
    shutil.copy(Path(__file__), out / "gpu_bench.py")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
