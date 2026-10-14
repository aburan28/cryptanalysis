#!/usr/bin/env python3
"""Replay canon-n131-20261014 under protocol.json.

Builds the crate (offline, locked), then writes into results/:
  build_receipt.json  toolchain, host, source and binary digests
  tests.txt           cargo test output (small-n exhaustive, fmul check)
  asm_check.json      conditional-jump audit of every arm
  exactness.json      n = 131 exactness
  metrics_uniform.json, metrics_structured.json
  instructions.json   perf attempt + cachegrind Ir per word
  wallclock.json      UNISOLATED exploratory timings

usage: python3 run.py [--quick]     (--quick shrinks every count, for smoke tests only)
Set CARGO_TARGET_DIR to share a build directory.
"""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
QUICK = "--quick" in sys.argv
P = json.load(open(os.path.join(HERE, "protocol.json")))
TARGET = os.environ.get("CARGO_TARGET_DIR", os.path.join(HERE, "target"))
BIN = os.path.join(TARGET, "release")
ARMS = ["exhaustive", "gap_scan", "refine_bf", "exhaustive_bf", "lift_scan", "null"]


def sh(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=HERE, **kw)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def q(n, small):
    return small if QUICK else n


def write(name, obj):
    with open(os.path.join(RES, name), "w") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")


def main():
    os.makedirs(RES, exist_ok=True)
    sh(["cargo", "build", "--release", "--locked", "--offline"])
    t = sh(["cargo", "test", "--release", "--locked", "--offline"])
    open(os.path.join(RES, "tests.txt"), "w").write(
        "\n".join(l for l in (t.stdout + t.stderr).splitlines()
                  if "test " in l or "small-n" in l or "Running" in l) + "\n")
    srcs = ["Cargo.toml", "Cargo.lock", "src/lib.rs", "src/bin/verify.rs", "src/bin/metrics.rs",
            "src/bin/bench.rs", "tests/small_n.rs", "protocol.json", "asm_check.py", "run.py"]
    write("build_receipt.json", {
        "rustc": sh(["rustc", "--version"]).stdout.strip(),
        "cargo": sh(["cargo", "--version"]).stdout.strip(),
        "valgrind": shutil.which("valgrind") and sh(["valgrind", "--version"]).stdout.strip(),
        "host": {"machine": platform.machine(), "kernel": platform.release(),
                 "cpu": next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo")
                              if l.startswith("model name")), None),
                 "nproc": os.cpu_count(), "isolation": "none (cloud agent VM, shared, unpinned)"},
        "source_sha256": {s: sha(os.path.join(HERE, s)) for s in srcs},
        "binary_sha256": {b: sha(os.path.join(BIN, b)) for b in ["verify", "metrics", "bench"]},
        "quick": QUICK,
    })

    # asm audit
    a = subprocess.run([sys.executable, "asm_check.py", os.path.join(BIN, "bench"),
                        os.path.join(RES, "asm_check.json")], cwd=HERE, capture_output=True, text=True)
    print(a.stdout)
    if a.returncode != 0:
        sys.exit("asm check failed")
    audit = json.load(open(os.path.join(RES, "asm_check.json")))
    leaf = [x for x in ARMS if audit[x]["calls"] != 0]
    if leaf:  # self Ir of the symbol would miss the callees
        sys.exit(f"arms with calls, Ir would be incomplete: {leaf}")

    # exactness
    ex = P["exactness"]
    v = sh([os.path.join(BIN, "verify"), str(q(ex["n131_uniform"]["words"], 20000)),
            str(ex["n131_uniform"]["seed"]), str(q(ex["oracle"]["words"], 2000))])
    write("exactness.json", json.loads(v.stdout))

    # deterministic counts
    m = P["metrics"]["counts"]
    for d, w, s in [("uniform", m["words_uniform"], m["seed_uniform"]),
                    ("structured", m["words_structured"], m["seed_structured"])]:
        r = sh([os.path.join(BIN, "metrics"), d, str(q(w, 20000)), str(s)])
        write(f"metrics_{d}.json", json.loads(r.stdout))

    # instruction counts
    ins = P["metrics"]["instructions"]
    words = q(ins["words"], 2000)
    perf = shutil.which("perf")
    out = {"words": words, "unit": ins["unit"]}
    if perf:
        try:
            r = subprocess.run([perf, "stat", "-x,", "-e", "instructions:u", os.path.join(BIN, "bench"),
                                "null", "uniform", "1000", "1", "0"], capture_output=True, text=True)
            out["perf"] = {"available": r.returncode == 0, "stderr": r.stderr[-500:]}
        except OSError as e:
            out["perf"] = {"available": False, "error": str(e)}
    else:
        out["perf"] = {"available": False, "error": "perf: command not found on this host"}
    rows = []
    for d, seed in [("uniform", ins["seeds"]["uniform"]), ("structured", ins["seeds"]["structured"])]:
        for arm in ARMS + ["fmul"]:
            if arm == "fmul" and d == "structured":
                continue
            f = os.path.join(RES, f"cg.{arm}.{d}.out")
            sh(["valgrind", "--tool=cachegrind", "--cache-sim=no", f"--cachegrind-out-file={f}",
                os.path.join(BIN, "bench"), arm, d, str(words),
                str(seed if arm != "fmul" else 7003), "0"])
            ann = sh(["cg_annotate", f]).stdout
            sym = "fmul131_clmul" if arm == "fmul" else f"canon131_{arm}"
            ir = None
            for line in ann.splitlines():
                if re.search(rf"[:\s]{sym}\s*$", line):
                    ir = int(line.split()[0].replace(",", ""))
                    break
            os.remove(f)
            rows.append({"arm": arm, "distribution": d, "symbol": sym, "Ir_total": ir,
                         "Ir_per_word": ir / words if ir is not None else None})
    out["rows"] = rows
    write("instructions.json", out)

    # wall clock (UNISOLATED, exploratory)
    wc = []
    wwords, reps = q(1000000, 20000), q(11, 3)
    for d, seed in [("uniform", 9001), ("structured", 9002)]:
        for arm in ARMS + ["fmul"]:
            if arm == "fmul" and d == "structured":
                continue
            r = sh([os.path.join(BIN, "bench"), arm, d, str(wwords), str(seed), str(reps)])
            wc.append(json.loads(r.stdout))
    write("wallclock.json", {"label": "UNISOLATED exploratory wall clock; no isolation receipt; "
                             "not a speedup claim", "rows": wc})
    print("done")


if __name__ == "__main__":
    main()
