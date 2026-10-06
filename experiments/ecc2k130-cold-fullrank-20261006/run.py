#!/usr/bin/env python3
"""Execute preregistered public cold controls from the pinned crypto source."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "CONFIG.json").read_text())


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_source(source):
    p = CONFIG["producer"]
    expected = {
        "examples/koblitz_rank_fixture.rs": p["rank_fixture_sha256"],
        "examples/koblitz_rho_fixture.rs": p["rho_fixture_sha256"],
        "Cargo.toml": p["cargo_toml_sha256"],
        "Cargo.lock": p["cargo_lock_sha256"],
    }
    actual = {name: digest(source / name) for name in expected}
    if actual != expected:
        raise SystemExit(f"source digest mismatch: {actual}")
    return actual


def sampled_rss_bytes(pid):
    result = subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"RSS monitor failed for pid {pid}: {result.returncode} {result.stderr.strip()}")
    return int(result.stdout.strip()) * 1024


def run_child(argv, env, cwd, out, limit_seconds, cap_bytes):
    with (out.with_suffix(".stdout.jsonl")).open("wb") as stdout, (out.with_suffix(".stderr.txt")).open("wb") as stderr:
        start = time.monotonic_ns()
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
        timed_out = False
        memory_cap_exceeded = False
        monitor_error = None
        peak_sampled = 0
        while True:
            pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic_ns() - start >= limit_seconds * 1_000_000_000:
                timed_out = True
                proc.kill()
                _, status, usage = os.wait4(proc.pid, 0)
                break
            try:
                peak_sampled = max(peak_sampled, sampled_rss_bytes(proc.pid))
            except RuntimeError as error:
                # A process may finish between wait4 and ps; reap if so.
                pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
                if pid:
                    break
                monitor_error = str(error)
                proc.kill()
                _, status, usage = os.wait4(proc.pid, 0)
                break
            if peak_sampled > cap_bytes:
                memory_cap_exceeded = True
                proc.kill()
                _, status, usage = os.wait4(proc.pid, 0)
                break
            time.sleep(0.1)
        end = time.monotonic_ns()
        code = os.waitstatus_to_exitcode(status)
        proc.returncode = code
    peak_wait4 = int(usage.ru_maxrss if sys.platform == "darwin" else usage.ru_maxrss*1024)
    if peak_wait4 > cap_bytes:
        memory_cap_exceeded = True
    record = {
        "argv": argv,
        "binary_sha256": digest(Path(argv[0])),
        "environment_overrides": {key: env[key] for key in ("KIC_SHARED_FACTOR_LOG_PRECOMPUTATION", "KIC_RHO_FIXED_TARGET_SCALAR") if key in env},
        "exit_code": code,
        "timed_out": timed_out,
        "memory_cap_exceeded": memory_cap_exceeded,
        "rss_monitor_error": monitor_error,
        "rss_monitor": "ps_rss_100ms_fail_closed_plus_wait4_peak",
        "whole_process_wall_ms": (end-start)/1_000_000,
        "child_user_cpu_ms": usage.ru_utime*1000,
        "child_system_cpu_ms": usage.ru_stime*1000,
        "child_peak_rss_bytes": peak_wait4,
        "peak_sampled_rss_bytes": peak_sampled,
        "rss_cap_bytes": cap_bytes,
        "stdout_sha256": digest(out.with_suffix(".stdout.jsonl")),
        "stderr_sha256": digest(out.with_suffix(".stderr.txt")),
    }
    out.with_suffix(".resource.json").write_text(json.dumps(record, sort_keys=True, indent=2)+"\n")
    return record


def rows(path):
    result = []
    for line in path.read_text().splitlines():
        if line.strip():
            result.append(json.loads(line))
    return result


def one(rows_, kind, **where):
    found = [row for row in rows_ if row.get("kind") == kind and all(row.get(k) == v for k, v in where.items())]
    if len(found) != 1:
        raise ValueError(f"expected one {kind} {where}, found {len(found)}")
    return found[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_root.resolve()
    ambient_kic = {key: value for key, value in os.environ.items() if key.startswith("KIC_")}
    if ambient_kic:
        raise SystemExit("unexpected inherited KIC_* environment keys: " + ", ".join(sorted(ambient_kic)))
    source_hashes = check_source(source)
    binaries = {name: source / "target/release/examples" / f"koblitz_{name}_fixture" for name in ("rank", "rho")}
    if any(not path.is_file() for path in binaries.values()):
        raise SystemExit("build both pinned examples before running")
    args.out_dir.mkdir(parents=True, exist_ok=False)
    (args.out_dir / "CONFIG.json").write_bytes((HERE / "CONFIG.json").read_bytes())
    metadata = {
        "source_hashes": source_hashes,
        "producer_commit": CONFIG["producer"]["commit"],
        "binary_hashes": {name: digest(path) for name, path in binaries.items()},
        "host": {"platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(), "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(), "cargo": subprocess.check_output(["cargo", "--version"], text=True).strip()},
        "cpu_isolation": "unverified",
        "ambient_kic_environment": {},
    }
    (args.out_dir / "BUILD.json").write_text(json.dumps(metadata, sort_keys=True, indent=2)+"\n")
    cap = CONFIG["resource_cap_bytes"]
    for cell in CONFIG["curves"]:
        n = cell["n"]
        direct = args.out_dir / f"n{n}-direct"
        direct_argv = [str(binaries["rank"]), str(n), "0", str(cell["eta"][0]), str(cell["eta"][1]), str(cell["direct_seed"]), cell["pair_mode"], cell["target_mode"], cell["query_mode"], str(CONFIG["producer_fixture_count"])]
        direct_env = os.environ.copy()
        direct_env.update(CONFIG["direct_env"])
        direct_record = run_child(direct_argv, direct_env, source, direct, cell["direct_timeout_seconds"], cap)
        decision = {"n": n, "direct": direct_record, "rho": None, "status": "DIRECT_FAILED"}
        if direct_record["exit_code"] != 0 or direct_record["timed_out"] or direct_record["memory_cap_exceeded"] or direct_record["rss_monitor_error"]:
            (args.out_dir / f"n{n}-decision.json").write_text(json.dumps(decision, sort_keys=True, indent=2)+"\n")
            continue
        try:
            direct_rows = rows(direct.with_suffix(".stdout.jsonl"))
            pre = one(direct_rows, "relation_rank_summary", fixture_index=0)
            target = one(direct_rows, "relation_rank_summary", fixture_index=1)
            if pre.get("status") != "RANK_PLUS_32" or target.get("status") != "SHARED_FACTOR_LOG_ONE_RELATION" or not target.get("linear_solution_verified"):
                raise ValueError("full-rank preparation or target recovery missing")
            scalar = target["published_fixture_scalar"]
        except (ValueError, KeyError) as error:
            decision["status"] = "DIRECT_SCHEMA_OR_RECOVERY_FAILURE"
            decision["error"] = str(error)
            (args.out_dir / f"n{n}-decision.json").write_text(json.dumps(decision, sort_keys=True, indent=2)+"\n")
            continue
        rho = args.out_dir / f"n{n}-rho"
        rho_argv = [str(binaries["rho"]), str(n), "0", "signed_frobenius", "1", "packed", str(cell["rho_seed"])]
        rho_env = os.environ.copy()
        rho_env["KIC_RHO_FIXED_TARGET_SCALAR"] = str(scalar)
        rho_record = run_child(rho_argv, rho_env, source, rho, cell["rho_timeout_seconds"], cap)
        decision["rho"] = rho_record
        decision["status"] = "RHO_FAILED"
        if rho_record["exit_code"] == 0 and not rho_record["timed_out"] and not rho_record["memory_cap_exceeded"] and not rho_record["rss_monitor_error"]:
            try:
                rho_row = one(rows(rho.with_suffix(".stdout.jsonl")), "rho_public_fixture")
                if rho_row["published_q"] != target["published_q"] or rho_row["recovered_fixture_scalar"] != target["recovered_fixture_scalar"] or not rho_row.get("verified"):
                    raise ValueError("paired public point, scalar, or rho verification mismatch")
                decision["status"] = "PAIRED_PRODUCER_VERIFIED_PENDING_INDEPENDENT_REPLAY"
            except (ValueError, KeyError) as error:
                decision["status"] = "PAIRING_FAILURE"
                decision["error"] = str(error)
        (args.out_dir / f"n{n}-decision.json").write_text(json.dumps(decision, sort_keys=True, indent=2)+"\n")
        print(f"n={n} {decision['status']}", flush=True)


if __name__ == "__main__":
    main()
