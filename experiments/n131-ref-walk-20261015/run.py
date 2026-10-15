#!/usr/bin/env python3
"""Stages of the n131-ref-walk run (the workflow calls them in this order).

  run.py exact  <out>   build, cargo test, f131.h KATs regenerated (CLMUL on/off),
                        inputs regenerated, independent Python check, known-log
                        solves.  Exits nonzero on any failure: timing never starts.
  run.py time   <out>   paired alternating timing at n=131 then n=83, pinned to CPU 1
  run.py ir     <out>   cachegrind Ir per step, every arm, both degrees
  run.py solve  <out>   the n=83 completion panel (4 processes)
  run.py check  <out>   independent re-verification of every panel logarithm
"""
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TARGET = Path(os.environ.get("CARGO_TARGET_DIR", HERE / "target"))
BIN = TARGET / "release"
PROTO = json.loads((HERE / "protocol.json").read_text())


def sh(cmd, **kw):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(list(map(str, cmd)), check=True, text=True, capture_output=True, cwd=HERE, **kw)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def exact(out):
    rec = {}
    sh(["cargo", "build", "--release", "--offline", "--locked"])
    t = sh(["cargo", "test", "--release", "--offline", "--locked"])
    (out / "tests.txt").write_text(t.stdout + t.stderr)
    rec["cargo_test"] = [l for l in t.stdout.splitlines() if l.startswith("test result")]
    # KATs from the header itself
    kat = {}
    for name, src, nvec, ref in [("f131_kat", REPO / "experiments/canon-n131-loop-20261014/kat/f131_kat.cpp", 400,
                                  REPO / "experiments/canon-n131-loop-20261014/kat/f131_kat.txt"),
                                 ("point_kat", HERE / "kat/point_kat.cpp", 300, HERE / "kat/point_kat.txt")]:
        for clmul in (1, 0):
            exe = TARGET / f"{name}_clmul{clmul}"
            flags = ["-mpclmul"] if clmul else []
            sh(["g++", "-O2", *flags, f"-DECC_HOST_CLMUL={clmul}", "-DECC_TABLE_PIVOT_BYTES=1",
                "-I" + str(REPO / "ecc2k130"), src, "-o", exe])
            got = sh([exe, nvec]).stdout
            kat[f"{name}_clmul{clmul}"] = got == ref.read_text()
    kat["compiler"] = sh(["g++", "--version"]).stdout.splitlines()[0]
    rec["kat"] = kat
    sh([sys.executable, "make_inputs.py", "--check"])
    rec["inputs_regenerated_identical"] = True
    emit = sh([BIN / "emit", "inputs/n131_points.json"]).stdout
    (out / "emit.json").write_text(emit)
    kl = out / "known_logs.jsonl"
    kl.unlink(missing_ok=True)
    pc = PROTO["completion"]["known_log_positive_control"]
    def one(arm):
        part = out / f"known_logs_{arm}.jsonl"
        part.unlink(missing_ok=True)
        sh([BIN / "solve", "inputs/known_logs.json", arm, pc["seed_base"], pc["seeds"], 64, 31, 0, 4, part])
        return part.read_text()
    with ThreadPoolExecutor(4) as ex:
        kl.write_text("".join(ex.map(one, pc["arms"])))
    for arm in pc["arms"]:
        (out / f"known_logs_{arm}.jsonl").unlink()
    chk = sh([sys.executable, "check_points.py", out / "emit.json", "kat/point_kat.txt",
              out / "independent_check_exact.json", kl])
    rows = [json.loads(l) for l in kl.read_text().splitlines()]
    rec["known_log_solves"] = len(rows)
    rec["known_log_all_match"] = all(r["known_match"] is True and r["verified"] for r in rows)
    rec["independent_check"] = json.loads((out / "independent_check_exact.json").read_text())
    rec["sources_sha256"] = {str(p.relative_to(HERE)): sha(p) for p in sorted(HERE.glob("src/**/*.rs"))
                             + [HERE / "tests/exact.rs", HERE / "protocol.json", HERE / "kat/point_kat.cpp"]}
    rec["binaries_sha256"] = {b: sha(BIN / b) for b in ("bench", "solve", "emit")}
    rec["pass"] = (all(v for k, v in kat.items() if k != "compiler") and rec["known_log_all_match"]
                   and rec["independent_check"]["pass"] and all(" 0 failed" in l for l in rec["cargo_test"]))
    (out / "exactness.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: rec[k] for k in ("kat", "known_log_all_match", "pass")}))
    if not rec["pass"]:
        sys.exit("exactness gate failed: no timing")


def timing(out):
    t = PROTO["timing"]
    for n in (131, 83):
        rows = out / f"timing_n{n}.jsonl"
        with open(out / f"timing_n{n}.stderr.txt", "w") as err:
            subprocess.run(["taskset", "-c", str(t["cpu"]), str(BIN / "bench"), str(n), f"inputs/n{n}_points.json",
                            str(t["steps_per_lane_per_block"][str(n)]), str(t["rounds"]), str(rows)],
                           check=True, cwd=HERE, stderr=err)


def ir(out):
    res = []
    lo, hi = PROTO["timing"]["ir"]["steps_per_lane"]
    for n in (131, 83):
        for arm in PROTO["timing"]["arms"]:
            v = {}
            for steps in (lo, hi):
                cg = out / f"cg.{n}.{arm}.{steps}.out"
                r = subprocess.run(["valgrind", "--tool=cachegrind", "--cache-sim=no", f"--cachegrind-out-file={cg}",
                                    str(BIN / "bench"), str(n), f"inputs/n{n}_points.json", str(steps), "ir", arm],
                                   cwd=HERE, capture_output=True, text=True, check=True)
                stat = json.loads(r.stdout.strip().splitlines()[-1])
                total = next(int(l.split()[1]) for l in cg.read_text().splitlines() if l.startswith("summary:"))
                v[steps] = (total, stat)
                cg.unlink()
            per = (v[hi][0] - v[lo][0]) / (64 * (hi - lo))
            res.append({"n": n, "arm": arm, "ir_lo": v[lo][0], "ir_hi": v[hi][0], "ir_per_step": per,
                        "stats_hi": v[hi][1]})
            print(n, arm, round(per, 1), flush=True)
    (out / "ir.json").write_text(json.dumps(res, indent=1))


def solve(out):
    c = PROTO["completion"]
    rows = out / "panel_solves.jsonl"
    rows.unlink(missing_ok=True)
    jobs = []
    for arm in c["arms"]:
        for lo in range(0, 64, 8):
            jobs.append((arm, lo))
    def one(job):
        arm, lo = job
        part = out / f"part_{arm}_{lo}.jsonl"
        part.unlink(missing_ok=True)
        sh([BIN / "solve", "inputs/panel64.json", arm, c["seed_base"], c["seeds_per_target"], 64, 31, lo, lo + 8, part])
        return part
    with ThreadPoolExecutor(c["processes"]) as ex:
        parts = list(ex.map(one, jobs))
    with open(rows, "w") as f:
        for p in parts:
            f.write(p.read_text())
            p.unlink()


def check(out):
    r = subprocess.run([sys.executable, "check_points.py", str(out / "emit.json"), "kat/point_kat.txt",
                        str(out / "independent_check_panel.json"), str(out / "panel_solves.jsonl"),
                        str(out / "known_logs.jsonl")], cwd=HERE)
    if r.returncode:
        sys.exit("independent check of the panel logarithms failed")


if __name__ == "__main__":
    stage, out = sys.argv[1], Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    {"exact": exact, "time": timing, "ir": ir, "solve": solve, "check": check}[stage](out)
