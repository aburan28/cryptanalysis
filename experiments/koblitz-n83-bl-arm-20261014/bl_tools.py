#!/usr/bin/env python3
"""Shared helpers: the BL binaries' command lines, pinned launches, digests and the cost model.

Nothing here computes a measured result. `predict_online_steps` and
`predict_plain_steps` are the frozen heuristic model (protocol.json `model`)
the positive control and the secondary n=83 check compare counts against.
"""

import hashlib
import json
import math
import os
import resource
import subprocess
import time
from pathlib import Path

BASE_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "RAYON_NUM_THREADS": "1",
            "KIC_THREADS": "1", "KIC_RHO_THREADS": "1", "OMP_NUM_THREADS": "1"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_lines(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def precompute_command(spec, bin_dir, curve, dp_bits, bl_jump_seed, precompute_seed, table_out, stop):
    """(argv, env) of one precomputation. `stop` is {"budget_ms"|"stop_steps"|"stop_rounds": value}."""
    (key, value), = stop.items()
    n, a = curve
    if spec["family"] == "rung3":
        env = dict(BASE_ENV, KIC_BL_MODE="precompute", KIC_RHO_RUNG="3", KIC_RHO_LANES=str(spec["lanes"]),
                   KIC_RHO_DP_BITS=str(dp_bits), KIC_BL_JUMP_SEED=str(bl_jump_seed),
                   KIC_BL_PRECOMPUTE_SEED=str(precompute_seed), KIC_BL_TABLE_OUT=str(table_out))
        env[{"budget_ms": "KIC_BL_BUDGET_MS", "stop_steps": "KIC_BL_STOP_STEPS",
             "stop_rounds": "KIC_BL_STOP_ROUNDS"}[key]] = str(value)
        return [str(Path(bin_dir) / "bl_rung3"), str(n), str(a), "signed_frobenius", "1", "0"], env
    argv = [str(Path(bin_dir) / "bl_sg"), "precompute", "--curve", "%d,%d" % (n, a), "--field", spec["field"],
            "--lanes", str(spec["lanes"]), "--dp-bits", str(dp_bits), "--bl-jump-seed", str(bl_jump_seed),
            "--precompute-seed", str(precompute_seed), "--table-out", str(table_out),
            "--" + key.replace("_", "-"), str(value)]
    return argv, dict(BASE_ENV)


def verify_command(spec, bin_dir, curve, dp_bits, table, blake3_hex, threads):
    n, a = curve
    if spec["family"] == "rung3":
        env = dict(BASE_ENV, KIC_BL_MODE="verify-table", KIC_RHO_RUNG="3", KIC_RHO_LANES=str(spec["lanes"]),
                   KIC_RHO_DP_BITS=str(dp_bits), KIC_BL_TABLE_IN=str(table), KIC_BL_TABLE_BLAKE3=blake3_hex,
                   KIC_BL_VERIFY_THREADS=str(threads))
        return [str(Path(bin_dir) / "bl_rung3"), str(n), str(a), "signed_frobenius", "1", "0"], env
    return [str(Path(bin_dir) / "bl_sg"), "verify-table", "--curve", "%d,%d" % (n, a), "--field", spec["field"],
            "--lanes", str(spec["lanes"]), "--dp-bits", str(dp_bits), "--table", str(table),
            "--table-blake3", blake3_hex, "--threads", str(threads)], dict(BASE_ENV)


def online_control_command(spec, bin_dir, curve, dp_bits, bl_jump_seed, walk_seed, scalar, table=None, blake3_hex=None):
    """A known-answer online solve (positive control): BL with `table`, plain rho without."""
    n, a = curve
    if spec["family"] == "rung3":
        env = dict(BASE_ENV, KIC_RHO_RUNG="3", KIC_RHO_LANES=str(spec["lanes"]), KIC_RHO_DP_BITS=str(dp_bits),
                   KIC_BL_JUMP_SEED=str(bl_jump_seed), KIC_RHO_EXPLICIT_SCALAR=str(scalar))
        if table is not None:
            env.update(KIC_BL_TABLE_IN=str(table), KIC_BL_TABLE_BLAKE3=blake3_hex)
        return [str(Path(bin_dir) / "bl_rung3"), str(n), str(a), "signed_frobenius", "1", str(walk_seed)], env
    argv = [str(Path(bin_dir) / "bl_sg"), "online", "--curve", "%d,%d" % (n, a), "--field", spec["field"],
            "--lanes", str(spec["lanes"]), "--dp-bits", str(dp_bits), "--bl-jump-seed", str(bl_jump_seed),
            "--walk-seed", str(walk_seed), "--scalar", str(scalar)]
    if table is not None:
        argv += ["--table", str(table), "--table-blake3", blake3_hex]
    return argv, dict(BASE_ENV)


def parse_online(spec, stdout):
    """The fields the control needs from one online run (either family)."""
    lines = json_lines(stdout)
    if spec["family"] == "rung3":
        fixture = ([r for r in lines if r.get("kind") == "rho_ks_batch_fixture"] or [{}])[-1]
        bl = ([r for r in lines if r.get("kind") == "bl_online_fixture"] or [{}])[-1]
        return {"verified": fixture.get("verified") is True and
                fixture.get("recovered_fixture_scalar") == fixture.get("published_fixture_scalar"),
                "recovered": fixture.get("recovered_fixture_scalar"), "steps": fixture.get("walk_steps"),
                "solved_by": bl.get("solved_by"), "table_entries_loaded": bl.get("table_entries_loaded")}
    record = ([r for r in lines if r.get("kind") == "bl_online"] or [{}])[-1]
    return {"verified": record.get("verified") is True and record.get("recovered_scalar") == record.get("planted_scalar"),
            "recovered": record.get("recovered_scalar"), "steps": record.get("walk_steps"),
            "solved_by": record.get("solved_by"), "table_entries_loaded": record.get("table_entries_loaded")}


def run_pinned(argv, env, cpu, stdout_path=None, timeout=None):
    """Run one process on `cpu`; returns (returncode, stdout, stderr, wall_s, child rusage delta)."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic_ns()
    proc = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            preexec_fn=(lambda: os.sched_setaffinity(0, {cpu})) if cpu is not None else None)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    wall_s = (time.monotonic_ns() - started) / 1e9
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    out, err = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    if stdout_path:
        Path(stdout_path).write_text(out)
    usage = {"user_s": after.ru_utime - before.ru_utime, "system_s": after.ru_stime - before.ru_stime,
             "max_rss_kib_children": after.ru_maxrss}
    return proc.returncode, out, err, wall_s, usage


def classes(r, automorphisms):
    """Number of signed-Frobenius classes of nonzero subgroup points."""
    return (int(r) - 1) / int(automorphisms)


def predict_plain_steps(r, automorphisms, lanes, dp_bits):
    """Frozen model, plain rho: sqrt(pi*l/2) collision steps plus one lane round per DP length (lanes * 2^dp)."""
    ell = classes(r, automorphisms)
    return math.sqrt(math.pi * ell / 2.0) + lanes * 2 ** dp_bits


def predict_online_steps(r, automorphisms, lanes, dp_bits, covered):
    """Frozen model, BL online with `covered` precomputed trail points (random-mapping heuristic).

    A fresh walk step lands on a precomputed trail with probability c/l and the
    walk's own earlier points give the rho hazard t/l, so the first merge comes
    after E[t] = sqrt(pi*l/2) * exp(c^2/2l) * erfc(c/sqrt(2l)) steps (= l/c for
    c >> sqrt(l), = plain rho at c = 0); detecting it costs about one walk length
    per lane, lanes * 2^dp steps.
    """
    ell = classes(r, automorphisms)
    z = covered / math.sqrt(2.0 * ell)
    # exp(z^2) * erfc(z), evaluated stably for large z.
    if z < 25:
        scaled = math.exp(z * z) * math.erfc(z)
    else:
        scaled = 1.0 / (z * math.sqrt(math.pi)) * (1 - 1 / (2 * z * z) + 3 / (4 * z ** 4))
    return math.sqrt(math.pi * ell / 2.0) * scaled + lanes * 2 ** dp_bits
