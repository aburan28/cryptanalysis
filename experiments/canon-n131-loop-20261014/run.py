#!/usr/bin/env python3
"""Local replay of canon-n131-loop-20261014 (everything except the Tier 1 timing).

Writes into results/:
  build_receipt.json  toolchain, host, source and binary digests, protocol hash
  tests.txt           cargo test (field KAT, Frobenius rotation, table, small loop)
  kat_check.json      kat/f131_kat.txt regenerated from ecc2k130/src/f131.h (clmul on and off)
  exactness.json      loop_verify over the full pass length of every workload
  counts.json         cachegrind Ir, Bc, Bcm (modelled), Bi, Bim per key, per arm and workload
  smoke/              a loop_bench + analyze.py SMOKE run (script test; no timing statement)

usage: python3 run.py [--skip-counts] [--skip-smoke] [--results DIR]
Set CARGO_TARGET_DIR to share a build directory.
"""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
RES = os.path.join(HERE, "results")
if "--results" in sys.argv:  # CI writes under results/ci/<run>/ instead
    RES = os.path.abspath(sys.argv[sys.argv.index("--results") + 1])
TARGET = os.environ.get("CARGO_TARGET_DIR", os.path.join(HERE, "target"))
BIN = os.path.join(TARGET, "release")
P = json.load(open(os.path.join(HERE, "protocol.json")))
ARMS = ["null", "exhaustive", "gap_scan", "refine_bf", "exhaustive_bf", "lift_scan", "lift_scan_aa"]
SRCS = ["Cargo.toml", "Cargo.lock", ".cargo/config.toml", "src/lib.rs", "src/bin/loop_verify.rs",
        "src/bin/loop_bench.rs", "src/bin/loop_counts.rs", "tests/field.rs", "kat/f131_kat.cpp",
        "kat/f131_kat.txt", "protocol.json", "run.py", "analyze.py", "receipt.py"]
DEP = ["../canon-n131-20261014/src/lib.rs", "../canon-n131-20261014/Cargo.toml",
       "../../ecc2k130/src/f131.h"]


def sh(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=HERE, **kw)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def write(name, obj):
    path = os.path.join(RES, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")


def kat_check():
    out = {}
    tmp = os.path.join(TARGET, "kat")
    os.makedirs(tmp, exist_ok=True)
    ref = open(os.path.join(HERE, "kat", "f131_kat.txt")).read()
    for clmul in ["1", "0"]:
        exe = os.path.join(tmp, f"f131_kat_clmul{clmul}")
        flags = ["-mpclmul"] if clmul == "1" else []
        sh(["g++", "-O2", *flags, f"-DECC_HOST_CLMUL={clmul}", "-DECC_TABLE_PIVOT_BYTES=1",
            "-I" + os.path.join(REPO, "ecc2k130"), "kat/f131_kat.cpp", "-o", exe])
        got = sh([exe, str(len(ref.splitlines()))]).stdout
        out[f"ECC_HOST_CLMUL={clmul}"] = {"vectors": len(got.splitlines()), "identical_to_committed": got == ref}
    out["compiler"] = sh(["g++", "--version"]).stdout.splitlines()[0]
    out["header_sha256"] = sha(os.path.join(REPO, "ecc2k130", "src", "f131.h"))
    write("kat_check.json", out)
    if not all(v["identical_to_committed"] for k, v in out.items() if k.startswith("ECC")):
        sys.exit("KAT mismatch")


def parse_cg(path):
    """Sum each function's events in a cachegrind out file."""
    events, fn, tot = None, None, {}
    for line in open(path):
        line = line.rstrip("\n")
        if line.startswith("events:"):
            events = line.split()[1:]
        elif line.startswith("fn="):
            fn = line[3:]
        elif line and line[0].isdigit() and fn is not None:
            v = [int(x) for x in line.split()[1:]]
            acc = tot.setdefault(fn, [0] * len(events))
            for i, x in enumerate(v):
                acc[i] += x
    return events, tot


def counts():
    keys = P["deterministic_counts"]["keys_per_symbol"]
    vg = shutil.which("valgrind")
    perf = shutil.which("perf")
    out = {"instrument": P["deterministic_counts"]["instrument"], "label": P["deterministic_counts"]["label"],
           "perf_available": bool(perf), "valgrind": vg and sh(["valgrind", "--version"]).stdout.strip(),
           "keys_per_symbol": keys, "workloads": {}}
    procs = []
    for w in P["workloads"]:
        name = w["workload"]
        cg = os.path.join(RES, f"cg.{name}.out")
        cmd = ["valgrind", "--tool=cachegrind", "--cache-sim=no", "--branch-sim=yes",
               f"--cachegrind-out-file={cg}", os.path.join(BIN, "loop_counts"), "protocol.json", name, str(keys)]
        print("+", " ".join(cmd), flush=True)
        procs.append((name, cg, subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                 text=True)))
    for name, cg, pr in procs:
        so, se = pr.communicate()
        if pr.returncode != 0:
            sys.exit(f"cachegrind {name} failed:\n{se}")
        work = next(w["work_muls"] for w in P["workloads"] if w["workload"] == name)
        events, tot = parse_cg(cg)
        W = {"summaries": so.strip().splitlines(), "arms": {}}
        for arm in ARMS:
            sym = f"loop_{arm}_w{work}"
            hit = [k for k in tot if k == sym or k.endswith("::" + sym)]
            if len(hit) != 1:
                sys.exit(f"{name}: symbol {sym} not found once in {cg}: {hit}")
            v = tot[hit[0]]
            W["arms"][arm] = {e + "_per_key": v[i] / keys for i, e in enumerate(events)}
            W["arms"][arm]["symbol"] = sym
        out["workloads"][name] = W
    write("counts.json", out)


def main():
    skip_counts = "--skip-counts" in sys.argv
    skip_smoke = "--skip-smoke" in sys.argv
    os.makedirs(RES, exist_ok=True)
    sh(["cargo", "build", "--release", "--locked", "--offline"])
    t = sh(["cargo", "test", "--release", "--locked", "--offline"])
    open(os.path.join(RES, "tests.txt"), "w").write(
        "\n".join(l for l in (t.stdout + t.stderr).splitlines() if "test " in l or "Running" in l) + "\n")
    kat_check()
    write("build_receipt.json", {
        "rustc": sh(["rustc", "--version"]).stdout.strip(),
        "cargo": sh(["cargo", "--version"]).stdout.strip(),
        "host": {"machine": platform.machine(), "kernel": platform.release(),
                 "cpu": next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo")
                              if l.startswith("model name")), None),
                 "nproc": os.cpu_count(), "isolation": ("GitHub-hosted runner; see receipt_pre.json / receipt_post.json" if os.environ.get("GITHUB_ACTIONS")
                               else "none (cloud agent VM, shared, unpinned)")},
        "protocol_sha256": sha(os.path.join(HERE, "protocol.json")),
        "source_sha256": {s: sha(os.path.join(HERE, s)) for s in SRCS},
        "dependency_sha256": {s: sha(os.path.join(HERE, s)) for s in DEP},
        "binary_sha256": {b: sha(os.path.join(BIN, b)) for b in ["loop_verify", "loop_bench", "loop_counts"]},
    })
    v = subprocess.run([os.path.join(BIN, "loop_verify"), "protocol.json"], cwd=HERE, capture_output=True,
                       text=True)
    print(v.stderr)
    ex = json.loads(v.stdout)
    write("exactness.json", ex)
    if v.returncode != 0 or not ex["pass"]:
        sys.exit("exactness failed")
    isolated_ir(os.path.join(RES, "isolated_ir.json"))
    if not skip_counts:
        counts()
    if not skip_smoke:
        sm = os.path.join(RES, "smoke")
        os.makedirs(sm, exist_ok=True)
        sh([os.path.join(BIN, "loop_bench"), "protocol.json", os.path.join(sm, "rows.jsonl"),
            "--rounds", "3", "--keys", "16384"])
        iso = os.path.join(RES, "isolated_ir.json")
        a = sh([sys.executable, "analyze.py", os.path.join(sm, "rows.jsonl"), os.path.join(sm, "analysis.json"), iso])
        print(a.stdout)


def isolated_ir(path):
    """Uniform-word Ir per word from canon-n131's committed instructions.json."""
    d = json.load(open(os.path.join(HERE, "..", "canon-n131-20261014", "results", "instructions.json")))
    out = {r["arm"]: r["Ir_per_word"] for r in d["rows"]
           if r["distribution"] == "uniform" and r["arm"] not in ("null", "fmul")}
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    return out


if __name__ == "__main__":
    main()
