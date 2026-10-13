#!/usr/bin/env python3
"""Capture paired table-accounting audits and the observable placement state."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import time

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def command(*args: str) -> str | None:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def read(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return None


def ps_snapshot() -> list[dict]:
    raw = command("ps", "-A", "-o", "%cpu=,comm=") or ""
    rows = []
    for line in raw.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            cpu = float(parts[0])
        except ValueError:
            continue
        if cpu >= 1.0:
            rows.append({"cpu_percent_snapshot": cpu, "comm": Path(parts[1]).name})
    return sorted(rows, key=lambda item: -item["cpu_percent_snapshot"])[:12]


def mac_environment() -> dict:
    raw = command("system_profiler", "SPHardwareDataType", "-json")
    overview = json.loads(raw)["SPHardwareDataType"][0] if raw else {}
    get = lambda key: command("sysctl", "-n", key)
    cache = {}
    for tier in (0, 1):
        prefix = f"hw.perflevel{tier}."
        cache[f"perflevel{tier}"] = {
            name: get(prefix + name)
            for name in ("name", "physicalcpu", "logicalcpu", "l1icachesize",
                         "l1dcachesize", "l2cachesize", "cpusperl2")
        }
    return {
        "cpu_vendor": "Apple",
        "reported_cpu_model": overview.get("chip_type", "unknown"),
        "microarchitecture": "unknown beyond reported chip type",
        "architecture": platform.machine(),
        "machine_model": overview.get("machine_model", "unknown"),
        "exposed_physical_cores": get("hw.physicalcpu"),
        "exposed_logical_threads": get("hw.logicalcpu"),
        "exposed_sockets": "one package reported by system_profiler",
        "cache_topology": cache,
        "kernel": platform.release(),
        "os": platform.platform(),
        "virtualization": "physical macOS host",
        "cpu_cgroup_limit": "not_applicable",
        "memory_cgroup_limit": "not_applicable",
        "physical_memory_bytes": get("hw.memsize"),
        "memory_technology": "unknown (not exposed by inspected host interfaces)",
        "memory_speed": "unknown (not exposed by inspected host interfaces)",
        "memory_channels": "unknown (not exposed by inspected host interfaces)",
        "allowed_cpus": "macOS does not expose a Linux-style process affinity mask",
        "allowed_memory_nodes": "macOS exposes no NUMA node mask; one unified-memory system",
        "selected_cpu_affinity": "system scheduler default; no pinning",
        "selected_memory_policy": "system default; no NUMA binding",
        "page_placement_interface": "unavailable: no /proc/PID/numa_maps on macOS",
        "cpu_throttling_counter": "not exposed for this process",
    }


def linux_environment() -> dict:
    cpuinfo = read("/proc/cpuinfo") or ""
    first = cpuinfo.split("\n\n", 1)[0]
    cpu_fields = dict(line.split(":", 1) for line in first.splitlines() if ":" in line)
    cpu_fields = {key.strip(): value.strip() for key, value in cpu_fields.items()}
    cache = {}
    for index in sorted(Path("/sys/devices/system/cpu/cpu0/cache").glob("index*")):
        cache[index.name] = {
            name: read(str(index / name))
            for name in ("level", "type", "size", "shared_cpu_list")
        }
    status = read("/proc/self/status") or ""
    status_fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    status_fields = {key.strip(): value.strip() for key, value in status_fields.items()}
    cgroup = Path("/sys/fs/cgroup")
    return {
        "cpu_vendor": cpu_fields.get("CPU implementer", "unknown"),
        "reported_cpu_model": cpu_fields.get("model name", "not exposed by guest"),
        "microarchitecture": "unknown in this virtualized guest",
        "architecture": platform.machine(),
        "exposed_physical_cores": "unknown; guest exposes logical CPUs only",
        "exposed_logical_threads": os.cpu_count(),
        "exposed_sockets": "unknown in guest",
        "cache_topology": cache or "not exposed by guest sysfs",
        "kernel": platform.release(),
        "os": platform.platform(),
        "virtualization": "Docker Desktop Linux VM" if Path("/.dockerenv").exists() else "unknown",
        "cpu_cgroup_limit": read(str(cgroup / "cpu.max")) or "unknown",
        "memory_cgroup_limit": read(str(cgroup / "memory.max")) or "unknown",
        "physical_memory_bytes": "unknown in VM",
        "memory_technology": "unknown in VM",
        "memory_speed": "unknown in VM",
        "memory_channels": "unknown in VM",
        "allowed_cpus": status_fields.get("Cpus_allowed_list", "unknown"),
        "allowed_memory_nodes": status_fields.get("Mems_allowed_list", "unknown"),
        "selected_cpu_affinity": sorted(os.sched_getaffinity(0)),
        "selected_memory_policy": "guest default; no explicit binding",
        "page_placement_interface": (
            "/proc/PID/numa_maps" if Path("/proc/self/numa_maps").exists()
            else "unavailable in guest kernel"
        ),
        "cpu_throttling_counter": read(str(cgroup / "cpu.stat")) or "unknown",
    }


def process_observation(pid: int) -> tuple[int | None, dict[str, int] | None]:
    rss_kib = None
    if platform.system() == "Linux":
        status = read(f"/proc/{pid}/status") or ""
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                rss_kib = int(line.split()[1])
        maps = read(f"/proc/{pid}/numa_maps")
        nodes = {}
        if maps:
            for token in maps.split():
                if token.startswith("N") and "=" in token:
                    node, count = token.split("=", 1)
                    if node[1:].isdigit() and count.isdigit():
                        nodes[node] = nodes.get(node, 0) + int(count)
        return rss_kib, nodes or None
    raw = command("ps", "-p", str(pid), "-o", "rss=")
    if raw and raw.strip().isdigit():
        rss_kib = int(raw.strip())
    return rss_kib, None


def audit(binary: Path, flag: str) -> dict:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic()
    process = subprocess.Popen([str(binary), flag], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    peak_sampled_rss_kib = 0
    observed_nodes = None
    samples = 0
    while process.poll() is None:
        rss, nodes = process_observation(process.pid)
        if rss is not None:
            peak_sampled_rss_kib = max(peak_sampled_rss_kib, rss)
        if nodes:
            observed_nodes = nodes
        samples += 1
        time.sleep(0.05)
    stdout, stderr = process.communicate()
    elapsed = time.monotonic() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if process.returncode != 0:
        raise RuntimeError(f"{flag} exited {process.returncode}: {stderr[:400]}")
    fields = dict(token.split("=", 1) for token in stdout.split() if "=" in token)
    expected_residues = "81796" if flag == "--axis286-audit" else "65536"
    if fields.get("verified") != "1" or fields.get("residues") != expected_residues:
        raise RuntimeError(f"unverified audit: {stdout[:400]}")
    return {
        "binary_sha256": digest(binary), "command_flag": flag,
        "stdout": stdout.strip(), "stdout_sha256": sha256(stdout.encode()).hexdigest(),
        "stderr_sha256": sha256(stderr.encode()).hexdigest(),
        "exit_code": process.returncode,
        "point_entries": int(fields["point_entries"]),
        "retained_bytes_exact_accounting": int(fields["retained_bytes"]),
        "wall_ms_incidental": round(elapsed * 1000, 3),
        "process_cpu_ms_incidental": round(
            1000 * (after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime), 3),
        "peak_sampled_rss_kib": peak_sampled_rss_kib or None,
        "page_placement_observed": observed_nodes or "unknown: interface unavailable or no sample",
        "placement_samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    env = mac_environment() if platform.system() == "Darwin" else linux_environment()
    record = {
        "schema": 1,
        "run_id": ("HEX256-STORAGE-MAC-20261012" if platform.system() == "Darwin"
                   else "HEX256-STORAGE-LINUX-20261012"),
        "status": "paired_storage_accounting_audits_verified",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "comparison_boundary": "exact retained table allocation from each native audit; no timing inference",
        "run_order": ["reference", "candidate"],
        "warmup": "none; fresh process and lazy table construction for each audit",
        "environment": env,
        "co_runners_at_start": ps_snapshot(),
        "search_receipt_sha256": digest(HERE / "search.json"),
        "replay_receipt_sha256": digest(HERE / "replay.json"),
        "runs": {
            "reference": audit(args.reference.resolve(), "--axis286-audit"),
            "candidate": audit(args.candidate.resolve(), "--hex-terminal-audit"),
        },
    }
    if (record["runs"]["reference"]["retained_bytes_exact_accounting"] != 14_309_128 or
            record["runs"]["candidate"]["retained_bytes_exact_accounting"] != 11_505_936):
        raise RuntimeError("table accounting differs from frozen replay")
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists():
            raise RuntimeError(f"output already exists: {args.output}")
        args.output.write_text(payload)
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
