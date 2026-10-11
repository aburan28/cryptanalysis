"""Driver for s4_bench.c: builds the native benchmark, runs the endpoint-reuse
regimes, records host information, and writes results/s4_bench.json.

Stage diagnostic only: wall time on a shared 4-vCPU cloud VM without the
isolated-benchmark receipt, so the ratios are exploratory (AGENTS.md "CPU
performance isolation gate").  Operation counts per pair are exact and do
not depend on the host.  candidate_id is null; no IC or ECDLP speedup is
claimed.

Regimes (W = 2^20 pairs unless stated):
  reuse_1        nL = nR = W        every endpoint in exactly one pair (loss case)
  fresh_right    nL = W/64, nR = W  left reused 64x, right endpoints fresh (loss case)
  reuse_16       nL = nR = W/16
  reuse_64       nL = nR = W/64
  indexed_1024   nL = nR = 1024, all 2^20 pairs visited
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys

from hardware_manifest import collect, proc_stat_snapshot, steal_delta

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "s4_bench.c")
BIN = os.path.join(HERE, "results", "s4_bench_bin")
OUT = os.path.join(HERE, "results", "s4_bench.json")
TRIALS = 7
SEED = 20261006
W = 1 << 20

REGIMES = [
    ("reuse_1", W, W, W),
    ("fresh_right", W // 64, W, W),
    ("reuse_16", W // 16, W // 16, W),
    ("reuse_64", W // 64, W // 64, W),
    ("indexed_1024", 1024, 1024, W),
]


def cpu_model() -> str:
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def main() -> None:
    os.makedirs(os.path.dirname(BIN), exist_ok=True)
    cc = ["gcc", "-O2", "-std=gnu11", "-o", BIN, SRC]
    subprocess.run(cc, check=True)
    gcc_v = subprocess.run(["gcc", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    rows = []
    for label, nL, nR, w in REGIMES:
        before = proc_stat_snapshot()
        load_before = os.getloadavg()
        proc = subprocess.run([BIN, str(nL), str(nR), str(w), str(TRIALS), str(SEED), label], capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stdout, proc.stderr, file=sys.stderr)
            raise SystemExit(f"benchmark failed in regime {label}")
        row = json.loads(proc.stdout.strip())
        row["host_during_run"] = {**steal_delta(before, proc_stat_snapshot()), "loadavg_before": load_before}
        rows.append(row)
        ev = {e["name"]: e for e in row["evaluators"]}
        tp = ev["two_product_2M"]["total_ms_median"]
        print(
            f"{label:13s} nL={nL:8d} nR={nR:8d} agree={row['all_evaluators_agree']} "
            + " ".join(f"{n.split('_')[0]}={e['total_ms_median']:.2f}ms" for n, e in ev.items())
            + f"  raw/twop={ev['raw_fused_7M1S']['total_ms_median']/tp:.2f} monic/twop={ev['monic_fused_3M1S']['total_ms_median']/tp:.2f}"
        )
    os.remove(BIN)
    res = {
        "status": "stage diagnostic; contended shared VM; exploratory wall time; candidate_id null",
        "host": {"cpu": cpu_model(), "machine": platform.machine(), "os": platform.platform(), "logical_cpus": os.cpu_count(), "compiler": gcc_v, "flags": "-O2 -std=gnu11", "isolation_receipt": None},
        "hardware_manifest": collect(),
        "execution": {"threads": 1, "affinity": "inherited (not pinned)", "warmup": "none beyond trial rotation; first trial of each regime counts", "pairing": "all four evaluators run inside one process per regime on identical inputs, order rotated per trial", "censored_runs": 0},
        "source_sha256": {os.path.basename(SRC): hashlib.sha256(open(SRC, "rb").read()).hexdigest()},
        "field": "p = 2^61 - 1, unsigned __int128 products, Mersenne reduction",
        "trials_per_regime": TRIALS,
        "statistic": "median over rotated trials of (precompute + pair loop); min also recorded",
        "seed": SEED,
        "regimes": rows,
    }
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
