#!/usr/bin/env python3
"""Serial, fail-closed Linux benchmark runner. No shell or network listener."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import shutil
import signal
import sqlite3
import statistics
import subprocess
import sys
import time
import uuid

CGROUP_ROOT = Path("/sys/fs/cgroup")
HOST_LOCK_PATH = Path("/run/lock/cryptanalysis-isolated-bench.lock")


def cpu_set(value):
    result = set()
    for part in value.strip().split(","):
        if not part:
            continue
        ends = part.split("-")
        if len(ends) == 1:
            low = high = int(ends[0])
        elif len(ends) == 2:
            low, high = map(int, ends)
        else:
            raise ValueError("invalid CPU/node list")
        if low < 0 or high < low:
            raise ValueError("invalid CPU/node range")
        result.update(range(low, high + 1))
    if not result:
        raise ValueError("empty CPU/node list")
    return result


def format_set(values):
    return ",".join(str(x) for x in sorted(values))


def read(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return None


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_write(path, value):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def tier(manifest):
    value = manifest.get("isolation", {}).get("tier", "tier0")
    if value not in ("tier0", "tier1"):
        raise ValueError("isolation tier must be tier0 or tier1")
    return value


def require_manifest(manifest):
    if manifest.get("schema") != 1:
        raise ValueError("manifest schema must be 1")
    isolation = manifest["isolation"]
    level = tier(manifest)
    cpus = cpu_set(isolation["cpus"])
    nodes = cpu_set(isolation["mem_nodes"])
    run_cpu = isolation.get("execution_cpu")
    if not isinstance(run_cpu, int) or run_cpu not in cpus:
        raise ValueError("execution_cpu must be one CPU in the declared CPU set")
    cgroup = Path(isolation["cgroup"])
    if not cgroup.is_absolute() or (level == "tier0" and cgroup == CGROUP_ROOT):
        raise ValueError("tier0 requires an absolute non-root cgroup")
    if cgroup != CGROUP_ROOT and not str(cgroup).startswith(str(CGROUP_ROOT) + "/"):
        raise ValueError("cgroup must be beneath /sys/fs/cgroup")
    if not (1 <= len(cpus) <= 256 and len(nodes) == 1):
        raise ValueError("invalid CPU or NUMA count")
    if level == "tier1":
        if len(cpus) != 1:
            raise ValueError("tier1 v1 requires one pinned exposed CPU")
        if manifest.get("repetitions", 1) < 5:
            raise ValueError("tier1 requires at least five alternating pairs")
        if len(manifest.get("cases", [])) != 1:
            raise ValueError("tier1 v1 requires one frozen workload case")
        allocation = isolation.get("allocation")
        if not isinstance(allocation, dict) or not all(
            isinstance(allocation.get(key), str) and allocation[key].strip()
            for key in ("provider", "instance_id", "receipt")
        ):
            raise ValueError("tier1 requires provider, instance_id and allocation receipt")
        receipt_path = Path(allocation["receipt"])
        if not receipt_path.is_absolute() or not receipt_path.is_file():
            raise ValueError("tier1 allocation receipt must be an absolute file")
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get("provider") != allocation["provider"] or
                receipt.get("instance_id") != allocation["instance_id"]):
            raise ValueError("tier1 allocation receipt identity mismatch")
    if not isinstance(manifest.get("cases"), list) or not manifest["cases"]:
        raise ValueError("cases must be nonempty")
    if not (1 <= manifest.get("repetitions", 1) <= 1000):
        raise ValueError("repetitions out of range")
    if not (0 < manifest.get("timeout_s", 0) <= 86400):
        raise ValueError("timeout_s must be in (0,86400]")
    workdir = Path(manifest["workdir"])
    if not workdir.is_absolute() or not workdir.is_dir():
        raise ValueError("workdir must be an existing absolute directory")
    seen = set()
    for case in manifest["cases"]:
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or "/" in case_id or case_id in seen:
            raise ValueError("invalid or duplicate case id")
        seen.add(case_id)
        for variant in ("reference", "candidate"):
            argv = case[variant]
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                raise ValueError("commands must be argv string arrays")
            binary = Path(argv[0])
            if not binary.is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK):
                raise ValueError("command must begin with an executable absolute file: " + argv[0])
            if binary.name == "sage" and binary != workdir / "sage":
                raise ValueError("Sage commands must use this repository's absolute ./sage launcher")
    if not isinstance(manifest.get("measurement_boundary"), str) or not manifest["measurement_boundary"]:
        raise ValueError("measurement_boundary must describe the benchmark's internal timer")
    metric_field = manifest.get("metric_field", "online_ms")
    if (not isinstance(metric_field, str) or not metric_field.endswith("_ms") or
        not metric_field[0].islower() or not all(
            char.islower() or char.isdigit() or char == "_" for char in metric_field)):
        raise ValueError("metric_field must name a nonnegative duration in milliseconds")
    if (metric_field != "online_ms" and
        (not isinstance(manifest.get("measurement_kind"), str) or
         not manifest["measurement_kind"].strip())):
        raise ValueError("non-online metric requires measurement_kind")
    if not isinstance(manifest.get("pair_fields"), list) or not manifest["pair_fields"]:
        raise ValueError("pair_fields must identify the frozen workload")
    for field in manifest["pair_fields"]:
        if not isinstance(field, str) or not field:
            raise ValueError("invalid pair field")
    if len(set(manifest["pair_fields"])) != len(manifest["pair_fields"]):
        raise ValueError("pair_fields must be unique")
    result_field = manifest.get("result_field")
    if not isinstance(result_field, str) or not result_field or any(
        char.isspace() or char == "=" for char in result_field
    ):
        raise ValueError("result_field must name the independently checked answer")
    for case in manifest["cases"]:
        expected = case.get("expected_fields")
        if not isinstance(expected, dict) or any(
            not isinstance(expected.get(field), str) or not expected[field]
            for field in manifest["pair_fields"]
        ):
            raise ValueError("each case needs expected_fields for every pair field")
        if not isinstance(case.get("expected_result"), str) or not case["expected_result"]:
            raise ValueError("each case needs an expected_result")
        if any(case["expected_result"] in case[variant][1:]
               for variant in ("reference", "candidate")):
            raise ValueError("expected_result must not be passed to solver argv")
    if not isinstance(manifest.get("artifacts"), list) or not manifest["artifacts"]:
        raise ValueError("artifacts must list at least one source or build file")
    for item in manifest["artifacts"]:
        path = Path(item)
        if not path.is_absolute() or not path.is_file():
            raise ValueError("artifact path must be an existing absolute file: " + str(item))
    if level == "tier1" and isolation["allocation"]["receipt"] not in manifest["artifacts"]:
        raise ValueError("tier1 allocation receipt must be hash-bound in artifacts")
    return cpus, nodes, cgroup


def virtualization():
    detector = shutil.which("systemd-detect-virt")
    if not detector:
        return "unknown"
    result = subprocess.run([detector], capture_output=True, text=True, timeout=5)
    if result.returncode == 1:
        return "none"
    return result.stdout.strip() or "unknown"


def version_line(executable):
    binary = shutil.which(executable)
    if not binary:
        return None
    try:
        result = subprocess.run([binary, "--version"], capture_output=True,
                                text=True, timeout=5)
        return (result.stdout or result.stderr).splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def cpu_identity():
    fields = {}
    for line in (read("/proc/cpuinfo") or "").splitlines():
        if ":" in line:
            key, value = (part.strip() for part in line.split(":", 1))
            fields.setdefault(key, value)
    for key in ("model name", "Hardware", "Processor"):
        if fields.get(key):
            return fields[key]
    arm = [fields[key] for key in ("CPU implementer", "CPU architecture",
                                  "CPU part", "CPU variant") if fields.get(key)]
    return "ARM " + "/".join(arm) if arm else None


def host_probe():
    info = {"host": platform.node(), "system": platform.system(),
            "kernel": platform.release(), "architecture": platform.machine(),
            "euid": os.geteuid(), "virtualization": virtualization() if sys.platform == "linux" else "not_linux",
            "numactl": shutil.which("numactl"), "cmdline": read("/proc/cmdline"),
            "compiler": version_line("cc"), "os_release": read("/etc/os-release"),
            "cgroup_controllers": read(CGROUP_ROOT / "cgroup.controllers"),
            "cgroup_isolated_cpus": read(CGROUP_ROOT / "cpuset.cpus.isolated"),
            "online_cpus": read("/sys/devices/system/cpu/online"),
            "nohz_full_cpus": read("/sys/devices/system/cpu/nohz_full"),
            "self_cgroup": read("/proc/self/cgroup"), "numa_nodes": {},
            "cpu_quota": read(CGROUP_ROOT / "cpu.max")}
    if sys.platform == "linux":
        info["affinity"] = sorted(os.sched_getaffinity(0))
        for node in Path("/sys/devices/system/node").glob("node[0-9]*"):
            info["numa_nodes"][node.name] = read(node / "cpulist")
    return info


def current_cgroup():
    for line in (read("/proc/self/cgroup") or "").splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[:2] == ["0", ""]:
            return (CGROUP_ROOT / parts[2].lstrip("/")).resolve()
    return None


def tier1_preflight(manifest, cpus, cgroup, evidence):
    """Qualify one pinned exposed CPU without asserting physical exclusivity."""
    problems = []
    allocation = manifest["isolation"]["allocation"]
    evidence["allocation"] = {"provider": allocation["provider"],
                              "instance_id": allocation["instance_id"],
                              "receipt_sha256": sha256(allocation["receipt"])}
    evidence["virtualization"] = virtualization()
    evidence["host_exclusivity_proved"] = False
    if not evidence.get("cpu_model"):
        problems.append("CPU model unavailable")
    try:
        cg = cgroup.resolve(strict=True)
        cg.relative_to(CGROUP_ROOT)
    except (OSError, ValueError):
        problems.append("declared cgroup is unavailable beneath cgroup v2")
        cg = cgroup
    actual_cgroup = current_cgroup()
    evidence["self_cgroup"] = str(actual_cgroup) if actual_cgroup else None
    if actual_cgroup != cg:
        problems.append("declared cgroup is not the runner's current cgroup")
    try:
        allowed = os.sched_getaffinity(0)
        evidence["runner_affinity"] = sorted(allowed)
        if manifest["isolation"]["execution_cpu"] not in allowed:
            problems.append("execution CPU is outside runner affinity")
    except OSError as exc:
        problems.append("cannot inspect runner affinity: " + str(exc))
    effective = read(cg / "cpuset.cpus.effective")
    evidence["cpuset.cpus.effective"] = effective
    try:
        if manifest["isolation"]["execution_cpu"] not in cpu_set(effective or ""):
            problems.append("execution CPU is outside effective cpuset")
    except ValueError:
        problems.append("effective cpuset unavailable")
    for name, keys in (("cpu.stat", ("nr_throttled", "throttled_usec")),
                       ("memory.events", ("max", "oom", "oom_kill"))):
        value = read(cg / name)
        evidence[name] = value
        if not value or not all(any(line.startswith(key + " ")
                                    for line in value.splitlines()) for key in keys):
            problems.append(name + " counters unavailable")
    for name in ("cpu.max", "memory.max", "cpu.pressure", "memory.current"):
        value = read(cg / name)
        evidence[name] = value
        if value is None:
            problems.append(name + " unavailable")
    cpu_max = (evidence.get("cpu.max") or "").split()
    if (len(cpu_max) != 2 or cpu_max[0] != "max" and not cpu_max[0].isdigit()
            or not cpu_max[1].isdigit()):
        problems.append("cpu.max is malformed")
    if not (evidence.get("memory.max") == "max" or
            (evidence.get("memory.max") or "").isdigit()):
        problems.append("memory.max is malformed")
    if not (evidence.get("memory.current") or "").isdigit():
        problems.append("memory.current is malformed")
    pressure = evidence.get("cpu.pressure") or ""
    if not any(line.startswith("some ") and "total=" in line
               for line in pressure.splitlines()):
        problems.append("cpu.pressure counters unavailable")
    execution_cpu = manifest["isolation"]["execution_cpu"]
    evidence["topology"][str(execution_cpu)] = read(
        f"/sys/devices/system/cpu/cpu{execution_cpu}/topology/thread_siblings_list")
    try:
        if execution_cpu not in cpu_set(evidence["topology"][str(execution_cpu)] or ""):
            problems.append("execution CPU sibling topology unavailable")
    except ValueError:
        problems.append("execution CPU sibling topology unavailable")
    evidence["frequency"][str(execution_cpu)] = {
        "current_khz": read(f"/sys/devices/system/cpu/cpu{execution_cpu}/cpufreq/scaling_cur_freq")}
    stat = counters({execution_cpu}, cg)
    if execution_cpu not in stat["per_cpu"]:
        problems.append("execution CPU steal-time counter unavailable")
    evidence["per_cpu_counter_available"] = execution_cpu in stat["per_cpu"]
    return {"ok": not problems, "tier": "tier1", "problems": problems,
            "evidence": evidence}


def preflight(manifest):
    cpus, nodes, cgroup = require_manifest(manifest)
    level = tier(manifest)
    problems = []
    evidence = {"timestamp_ns": time.time_ns(), "host": platform.node(),
                "kernel": platform.release(), "architecture": platform.machine(),
                "virtualization": "unknown", "cmdline": read("/proc/cmdline"),
                "compiler": version_line("cc"), "os_release": read("/etc/os-release"),
                "cpu_model": cpu_identity(),
                "cpus": sorted(cpus), "execution_cpu": manifest["isolation"]["execution_cpu"],
                "mem_nodes": sorted(nodes),
                "cgroup": str(cgroup), "topology": {}, "frequency": {},
                "irq_affinity_overlap": []}
    if sys.platform != "linux":
        problems.append("requires Linux; this host cannot certify CPU/NUMA isolation")
        return {"ok": False, "tier": level, "problems": problems, "evidence": evidence}
    if level == "tier1":
        return tier1_preflight(manifest, cpus, cgroup, evidence)
    if os.geteuid() != 0:
        problems.append("requires host root to inspect and enforce the isolated partition")
    evidence["virtualization"] = virtualization()
    if evidence["virtualization"] != "none":
        problems.append("bare-metal host control unproved: " + evidence["virtualization"])
    try:
        allowed = os.sched_getaffinity(0)
        evidence["runner_affinity"] = sorted(allowed)
        if allowed & cpus:
            problems.append("runner is permitted on benchmark CPUs; pin service to housekeeping CPUs")
    except OSError as exc:
        problems.append("cannot inspect runner affinity: " + str(exc))
    try:
        cg = cgroup.resolve(strict=True)
        cg.relative_to(CGROUP_ROOT)
    except (OSError, ValueError):
        problems.append("isolated cgroup does not exist beneath the unified hierarchy")
        cg = cgroup
    expected = {"cpuset.cpus.partition": "isolated",
                "cpuset.cpus.effective": cpus,
                "cpuset.cpus.exclusive.effective": cpus,
                "cpuset.mems.effective": nodes}
    for name, want in expected.items():
        actual = read(cg / name)
        evidence[name] = actual
        try:
            valid = actual == want if isinstance(want, str) else cpu_set(actual or "") == want
        except ValueError:
            valid = False
        if not valid:
            problems.append(name + " does not match requested isolation")
    processes = read(cg / "cgroup.procs")
    evidence["cgroup.procs"] = processes
    if processes is None or processes:
        problems.append("benchmark cgroup must be empty before dispatch")
    events = read(cg / "cgroup.events")
    evidence["cgroup.events"] = events
    if events is None or "populated 0" not in events.splitlines():
        problems.append("benchmark cgroup or a descendant contains processes")
    cpu_stat_text = read(cg / "cpu.stat")
    if not cpu_stat_text or not all(
        any(line.startswith(key + " ") for line in cpu_stat_text.splitlines())
        for key in ("nr_throttled", "throttled_usec")
    ):
        problems.append("cpu.stat throttling counters unavailable")
    memory_events = read(cg / "memory.events")
    if not memory_events or not all(
        any(line.startswith(key + " ") for line in memory_events.splitlines())
        for key in ("oom", "oom_kill")
    ):
        problems.append("memory.events unavailable")
    pressure = read(cg / "cpu.pressure")
    if not pressure or not any(line.startswith("some ") and "total=" in line
                               for line in pressure.splitlines()):
        problems.append("cpu.pressure unavailable")
    interrupts_text = read("/proc/interrupts")
    if not interrupts_text or not all(f"CPU{cpu}" in interrupts_text.splitlines()[0].split()
                                      for cpu in cpus):
        problems.append("per-CPU interrupt counters unavailable")
    ancestor = cg
    while str(ancestor).startswith(str(CGROUP_ROOT)):
        quota = read(ancestor / "cpu.max")
        if quota and not quota.startswith("max "):
            problems.append("CPU quota active at " + str(ancestor))
        if ancestor == CGROUP_ROOT:
            break
        ancestor = ancestor.parent
    for key, path in (("online", "/sys/devices/system/cpu/online"),
                      ("nohz_full", "/sys/devices/system/cpu/nohz_full"),
                      ("isolated_partitions", CGROUP_ROOT / "cpuset.cpus.isolated")):
        value = read(path)
        evidence[key] = value
        try:
            if not cpus <= cpu_set(value or ""):
                problems.append(key + " does not cover benchmark CPUs")
        except ValueError:
            problems.append(key + " unavailable or empty")
    for cpu in sorted(cpus):
        base = Path(f"/sys/devices/system/cpu/cpu{cpu}")
        siblings = read(base / "topology/thread_siblings_list")
        evidence["topology"][str(cpu)] = siblings
        try:
            if not cpu_set(siblings or "") <= cpus:
                problems.append(f"CPU {cpu} has an SMT sibling outside the partition")
        except ValueError:
            problems.append(f"CPU {cpu} sibling topology unavailable")
        containing_nodes = {node for node in nodes if (Path(f"/sys/devices/system/node/node{node}") / f"cpu{cpu}").exists()}
        if len(containing_nodes) != 1:
            problems.append(f"CPU {cpu} is not on exactly one requested NUMA node")
        freq = base / "cpufreq"
        governor = read(freq / "scaling_governor")
        low, high = read(freq / "scaling_min_freq"), read(freq / "scaling_max_freq")
        evidence["frequency"][str(cpu)] = {"governor": governor, "min_khz": low,
                                           "max_khz": high, "current_khz": read(freq / "scaling_cur_freq")}
        if governor != "performance" or not low or low != high:
            problems.append(f"CPU {cpu} frequency must be fixed with performance governor")
    if not shutil.which("numactl"):
        problems.append("numactl is required for explicit memory binding")
    irq_dir = Path("/proc/irq")
    if not irq_dir.exists():
        problems.append("IRQ affinity data unavailable")
    else:
        irq_paths = list(irq_dir.glob("[0-9]*/effective_affinity_list"))
        if not irq_paths:
            problems.append("no effective IRQ affinity files were exposed")
        for path in irq_paths:
            try:
                if cpu_set(read(path) or "") & cpus:
                    evidence["irq_affinity_overlap"].append(path.parent.name)
            except ValueError:
                pass
                problems.append("IRQ effective affinity unreadable: " + str(path))
        if evidence["irq_affinity_overlap"]:
            problems.append("IRQ effective affinity intersects benchmark CPUs")
    evidence["host_exclusivity_proved"] = not problems
    return {"ok": not problems, "tier": "tier0", "problems": problems,
            "evidence": evidence}


def counters(cpus, cgroup):
    stat = {}
    for line in (read("/proc/stat") or "").splitlines():
        cols = line.split()
        if cols and cols[0].startswith("cpu") and cols[0][3:].isdigit():
            cpu = int(cols[0][3:])
            if cpu in cpus:
                stat[cpu] = {"irq": int(cols[6]), "softirq": int(cols[7]),
                             "steal": int(cols[8])}
    lines = (read("/proc/interrupts") or "").splitlines()
    irq = {cpu: 0 for cpu in cpus}
    headings = []
    if lines:
        headings = [int(word[3:]) for word in lines[0].split()
                    if word.startswith("CPU") and word[3:].isdigit()]
    for line in lines[1:]:
        cols = line.split()
        for column, cpu in enumerate(headings, start=1):
            if cpu in cpus and column < len(cols):
                try:
                    irq[cpu] += int(cols[column])
                except ValueError:
                    pass
    def numeric_file(path):
        result = {}
        for line in (read(path) or "").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit():
                result[parts[0]] = int(parts[1])
        return result
    pressure = {}
    for line in (read(cgroup / "cpu.pressure") or "").splitlines():
        parts = line.split()
        if parts:
            for part in parts[1:]:
                if part.startswith("total="):
                    pressure[parts[0]] = int(part.split("=", 1)[1])
    thermal = {}
    for cpu in cpus:
        base = Path(f"/sys/devices/system/cpu/cpu{cpu}/thermal_throttle")
        thermal[cpu] = {name: read(base / name) for name in
                        ("core_throttle_count", "package_throttle_count")}
    return {"cpu_stat": numeric_file(cgroup / "cpu.stat"),
            "memory_events": numeric_file(cgroup / "memory.events"),
            "memory_current": read(cgroup / "memory.current"),
            "memory_peak": read(cgroup / "memory.peak"),
            "cpu_pressure_total": pressure,
            "memory_numa_stat": read(cgroup / "memory.numa_stat"),
            "per_cpu": stat, "interrupts": irq,
            "thermal_throttle": thermal,
            "frequency_khz": {cpu: read(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq")
                              for cpu in cpus}}


def noise(before, after, usage_before, usage_after, level="tier0"):
    problems = []
    def delta(section, key):
        return after[section].get(key, 0) - before[section].get(key, 0)
    for key in ("nr_throttled", "throttled_usec"):
        if delta("cpu_stat", key):
            problems.append("CPU throttling: " + key)
    for key in ("oom", "oom_kill"):
        if delta("memory_events", key):
            problems.append("memory event: " + key)
    if level == "tier1" and delta("memory_events", "max"):
        problems.append("memory event: max")
    if level == "tier0" and delta("cpu_pressure_total", "some"):
        problems.append("CPU pressure accrued")
    for cpu in before["per_cpu"]:
        if cpu not in after["per_cpu"]:
            problems.append(f"CPU {cpu} counter disappeared")
            continue
        for key in (("irq", "softirq", "steal") if level == "tier0" else ("steal",)):
            if after["per_cpu"][cpu][key] != before["per_cpu"][cpu][key]:
                problems.append(f"CPU {cpu} {key} time changed")
        if level == "tier0" and after["interrupts"].get(cpu) != before["interrupts"].get(cpu):
            problems.append(f"CPU {cpu} interrupt count changed")
        for key in ("core_throttle_count", "package_throttle_count"):
            old = before["thermal_throttle"][cpu][key]
            new = after["thermal_throttle"][cpu][key]
            if old is not None and new != old:
                problems.append(f"CPU {cpu} thermal throttle counter changed: {key}")
        old_freq = before["frequency_khz"].get(cpu)
        new_freq = after["frequency_khz"].get(cpu)
        if level == "tier0" and old_freq is not None and new_freq != old_freq:
            problems.append(f"CPU {cpu} frequency readback changed")
    if level == "tier0" and usage_after.ru_nivcsw > usage_before.ru_nivcsw:
        problems.append("involuntary context switches")
    if usage_after.ru_majflt > usage_before.ru_majflt:
        problems.append("major page faults")
    return problems


def output_fields(stdout, metric_field="online_ms"):
    for line in reversed(stdout.splitlines()):
        fields = {}
        for word in line.split():
            if "=" in word:
                key, value = word.split("=", 1)
                fields[key] = value
        if metric_field in fields:
            return fields
    return {}


def benchmark_env():
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
           "TZ": "UTC", "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1",
           "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
           "NUMEXPR_NUM_THREADS": "1"}
    if "HOME" in os.environ:
        env["HOME"] = os.environ["HOME"]
    return env


def one_run(argv, manifest, cpus, nodes, cgroup, folder, serial):
    health = preflight(manifest)
    if not health["ok"]:
        return {"serial": serial, "status": "rejected", "preflight": health,
                "command": argv}
    binary_before = sha256(argv[0])
    before = counters(cpus, cgroup)
    if set(before["per_cpu"]) != cpus or set(before["interrupts"]) != cpus:
        return {"serial": serial, "status": "invalid", "issues": ["CPU counters unavailable"],
                "command": argv, "before": before}
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    begin = time.monotonic_ns()
    run_cpu = manifest["isolation"]["execution_cpu"]
    level = tier(manifest)
    launcher = ([shutil.which("numactl"), "--membind=" + format_set(nodes),
                 "--physcpubind=" + str(run_cpu), "--"] + argv
                if level == "tier0" else argv)
    def child_setup():
        if level == "tier0":
            with (cgroup / "cgroup.procs").open("w") as stream:
                stream.write(str(os.getpid()))
        elif current_cgroup() != cgroup.resolve():
            raise RuntimeError("child cgroup changed before launch")
        os.sched_setaffinity(0, {run_cpu})
    try:
        proc = subprocess.Popen(launcher, cwd=manifest["workdir"], env=benchmark_env(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True,
                                preexec_fn=child_setup)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"serial": serial, "status": "invalid", "issues": ["launch failed: " + str(exc)],
                "command": argv, "before": before, "after": counters(cpus, cgroup)}
    def stop_child():
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    timed_out = False
    try:
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=manifest["timeout_s"])
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_child()
            stdout_bytes, stderr_bytes = proc.communicate()
    except BaseException:
        stop_child()
        proc.communicate()
        raise
    outer_ms = (time.monotonic_ns() - begin) / 1e6
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    after = counters(cpus, cgroup)
    stdout = stdout_bytes.decode("utf-8", "replace")
    stderr = stderr_bytes.decode("utf-8", "replace")
    stem = f"{serial:05d}"
    (folder / (stem + ".stdout.txt")).write_text(stdout)
    (folder / (stem + ".stderr.txt")).write_text(stderr)
    metric_field = manifest.get("metric_field", "online_ms")
    fields = output_fields(stdout, metric_field)
    issues = noise(before, after, usage_before, usage_after, level)
    if level == "tier0" and read(cgroup / "cgroup.procs"):
        issues.append("benchmark cgroup not empty after process exit")
        kill_file = cgroup / "cgroup.kill"
        if kill_file.exists():
            try:
                kill_file.write_text("1")
            except OSError as exc:
                issues.append("cgroup cleanup failed: " + str(exc))
    try:
        binary_after = sha256(argv[0])
    except OSError:
        binary_after = None
    if binary_after != binary_before:
        issues.append("benchmark executable changed during solve")
    postflight = preflight(manifest)
    if not postflight["ok"]:
        issues.append("post-run isolation changed: " + "; ".join(postflight["problems"]))
    metric = None
    try:
        metric = float(fields[metric_field])
        if not math.isfinite(metric) or metric <= 0:
            raise ValueError("invalid " + metric_field)
    except (KeyError, ValueError):
        issues.append("missing or invalid " + metric_field)
    if metric is not None and metric > outer_ms:
        issues.append(metric_field + " exceeds outer elapsed time")
    if fields.get("verified") != "1":
        issues.append("missing verified=1")
    if proc.returncode != 0:
        issues.append("nonzero exit status")
    if timed_out:
        issues.append("timeout")
    return {"serial": serial, "status": "valid" if not issues else "invalid",
            "tier": level, "issues": issues, "command": argv,
            "binary_sha256": binary_before,
            "returncode": proc.returncode, "timed_out": timed_out,
            "environment": benchmark_env(),
            "outer_ms": outer_ms, "metric_field": metric_field,
            "metric_ms": metric,
            "online_ms": metric if metric_field == "online_ms" else None,
            "child_cpu_user_ms": (usage_after.ru_utime - usage_before.ru_utime) * 1000,
            "child_cpu_system_ms": (usage_after.ru_stime - usage_before.ru_stime) * 1000,
            "child_peak_rss_kb_cumulative": usage_after.ru_maxrss,
            "child_involuntary_switches": usage_after.ru_nivcsw - usage_before.ru_nivcsw,
            "child_major_faults": usage_after.ru_majflt - usage_before.ru_majflt,
            "fields": fields, "before": before, "after": after,
            "postflight": postflight,
            "stdout_file": stem + ".stdout.txt", "stderr_file": stem + ".stderr.txt"}


def execute(manifest, output):
    cpus, nodes, cgroup = require_manifest(manifest)
    level = tier(manifest)
    output.mkdir(parents=True, exist_ok=False)
    json_write(output / "manifest.json", manifest)
    artifact_hashes_before = {path: sha256(path) for path in manifest["artifacts"]}
    binary_paths = {case[variant][0] for case in manifest["cases"]
                    for variant in ("reference", "candidate")}
    binary_hashes_before = {path: sha256(path) for path in sorted(binary_paths)}
    runner_hash_before = sha256(Path(__file__))
    health = preflight(manifest)
    json_write(output / "preflight.json", health)
    if not health["ok"]:
        summary = {"status": "rejected", "problems": health["problems"],
                   "tier": level,
                   "artifact_sha256": artifact_hashes_before,
                   "binary_sha256": binary_hashes_before,
                   "runner_sha256": runner_hash_before,
                   "paired_speedup": None, "valid_pairs": 0}
        json_write(output / "summary.json", summary)
        return summary
    rows = []
    pairs = []
    with (output / "runs.jsonl").open("w") as ledger, (output / "pairs.jsonl").open("w") as pair_ledger:
        for repeat in range(manifest.get("repetitions", 1)):
            for index, case in enumerate(manifest["cases"]):
                order = ("reference", "candidate") if (repeat + index) % 2 == 0 else ("candidate", "reference")
                pair = {}
                for variant in order:
                    row = one_run(case[variant], manifest, cpus, nodes, cgroup,
                                  output, len(rows) + 1)
                    row.update({"case": case["id"], "repeat": repeat, "variant": variant})
                    pair[variant] = row
                    rows.append(row)
                    ledger.write(json.dumps(row, sort_keys=True) + "\n")
                    ledger.flush()
                    os.fsync(ledger.fileno())
                    if row["status"] != "valid":
                        break
                issues = []
                if len(pair) != 2 or any(v["status"] != "valid" for v in pair.values()):
                    issues.append("incomplete or invalid solve")
                else:
                    mismatch = [field for field in manifest["pair_fields"]
                                if not pair["reference"]["fields"].get(field) or
                                pair["reference"]["fields"][field] != pair["candidate"]["fields"].get(field)]
                    if mismatch:
                        issues.append("pair mismatch: " + ",".join(mismatch))
                    mismatch = [field for field in manifest["pair_fields"]
                                if any(row["fields"].get(field) != case["expected_fields"][field]
                                       for row in pair.values())]
                    if mismatch:
                        issues.append("frozen-input mismatch: " + ",".join(mismatch))
                    if any(row["fields"].get(manifest["result_field"]) !=
                           case["expected_result"] for row in pair.values()):
                        issues.append("answer differs from frozen expected_result")
                record = {"case": case["id"], "repeat": repeat,
                          "run_serials": {variant: row["serial"] for variant, row in pair.items()},
                          "status": "valid" if not issues else "invalid", "issues": issues,
                          "speedup": ((pair["reference"].get("metric_ms") or
                                       pair["reference"].get("online_ms")) /
                                      (pair["candidate"].get("metric_ms") or
                                       pair["candidate"].get("online_ms"))) if not issues else None}
                pairs.append(record)
                pair_ledger.write(json.dumps(record, sort_keys=True) + "\n")
                pair_ledger.flush()
                os.fsync(pair_ledger.fileno())
    ratios = [pair["speedup"] for pair in pairs if pair["status"] == "valid"]
    expected = 2 * len(manifest["cases"]) * manifest.get("repetitions", 1)
    artifact_hashes_after = {path: sha256(path) for path in manifest["artifacts"]}
    artifacts_stable = artifact_hashes_after == artifact_hashes_before
    binary_hashes_after = {path: sha256(path) for path in sorted(binary_paths)}
    binaries_stable = binary_hashes_after == binary_hashes_before
    runner_stable = sha256(Path(__file__)) == runner_hash_before
    complete = (len(rows) == expected and len(pairs) == expected // 2 and
                len(ratios) * 2 == expected and artifacts_stable and
                binaries_stable and runner_stable)
    per_case = []
    for case in manifest["cases"]:
        case_ratios = [pair["speedup"] for pair in pairs
                       if pair["case"] == case["id"] and pair["status"] == "valid"]
        if len(case_ratios) == manifest.get("repetitions", 1):
            per_case.append(statistics.median(case_ratios))
    bootstrap95 = None
    if complete and len(per_case) >= 5:
        rng = random.Random(20261003)
        boot = sorted(statistics.median(per_case[rng.randrange(len(per_case))]
                                        for _ in per_case) for _ in range(10000))
        bootstrap95 = [boot[250], boot[9749]]
    pair_bootstrap95 = None
    if complete and level == "tier1":
        rng = random.Random(20261012)
        boot = sorted(statistics.median(ratios[rng.randrange(len(ratios))]
                                        for _ in ratios) for _ in range(10000))
        pair_bootstrap95 = [boot[250], boot[9749]]
    observed_ratio = statistics.median(per_case) if complete else None
    qualified = complete and (level == "tier0" or
                              pair_bootstrap95 is not None and pair_bootstrap95[0] > 1)
    allocation = manifest["isolation"].get("allocation", {})
    summary = {"status": "completed" if complete else "invalid",
               "tier": level,
               "provider": allocation.get("provider"),
               "instance_id": allocation.get("instance_id"),
               "allocation_receipt_sha256": (artifact_hashes_before.get(
                   allocation.get("receipt")) if level == "tier1" else None),
               "execution_cpu": manifest["isolation"]["execution_cpu"],
               "cgroup": str(cgroup),
               "observed_cpu_max": health["evidence"].get("cpu.max"),
               "observed_memory_max": health["evidence"].get("memory.max"),
               "host_exclusivity_proved": level == "tier0" and health["ok"],
               "speedup_qualified": qualified,
               "observed_ratio_median": observed_ratio,
               "metric_field": manifest.get("metric_field", "online_ms"),
               "measurement_kind": manifest.get("measurement_kind", "online"),
               "valid_pairs": len(ratios), "expected_pairs": expected // 2,
               "paired_speedup": observed_ratio if qualified else None,
               "bootstrap95_by_target": bootstrap95,
               "bootstrap95_by_pair": pair_bootstrap95,
               "artifact_sha256": artifact_hashes_before,
               "artifacts_stable": artifacts_stable,
               "binary_sha256": binary_hashes_before,
               "binaries_stable": binaries_stable,
               "runner_sha256": runner_hash_before,
               "runner_stable": runner_stable,
               "manifest_sha256": sha256(output / "manifest.json")}
    json_write(output / "summary.json", summary)
    return summary


@contextlib.contextmanager
def only_worker(queue_root):
    queue_root.mkdir(parents=True, exist_ok=True)
    with contextlib.ExitStack() as stack:
        lock_paths = [queue_root / "worker.lock"]
        if sys.platform == "linux":
            lock_paths.append(HOST_LOCK_PATH)
        for path in lock_paths:
            lock = stack.enter_context(path.open("a+"))
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("another benchmark worker holds lock " + str(path))
        yield


@contextlib.contextmanager
def job_slot(shared_job_lock):
    """Hold a lock shared with any other launcher for the whole job."""
    if shared_job_lock is None:
        yield
        return
    with shared_job_lock.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def database(queue_root):
    queue_root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(queue_root / "queue.sqlite3", timeout=30, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, "
               "created_ns INTEGER NOT NULL, started_ns INTEGER, finished_ns INTEGER, "
               "manifest TEXT NOT NULL, output TEXT, summary TEXT)")
    return db


def serve(queue_root, once=False, shared_job_lock=None):
    with only_worker(queue_root):
        db = database(queue_root)
        db.execute("UPDATE jobs SET status='interrupted', finished_ns=? WHERE status='running'",
                   (time.time_ns(),))
        while True:
            item = db.execute("SELECT id,manifest FROM jobs WHERE status='queued' "
                              "ORDER BY created_ns,id LIMIT 1").fetchone()
            if item is None:
                if once:
                    break
                time.sleep(1)
                continue
            job_id, raw = item
            with job_slot(shared_job_lock):
                db.execute("UPDATE jobs SET status='running',started_ns=? WHERE id=?",
                           (time.time_ns(), job_id))
                output = queue_root / "results" / job_id
                try:
                    summary = execute(json.loads(raw), output)
                    status = summary["status"]
                except Exception as exc:
                    summary = {"status": "error", "error": type(exc).__name__ + ": " + str(exc)}
                    status = "error"
                db.execute("UPDATE jobs SET status=?,finished_ns=?,output=?,summary=? WHERE id=?",
                           (status, time.time_ns(), str(output), json.dumps(summary), job_id))
            if once:
                break


def main():
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-root", type=Path, default=Path("/workspace/isolated-bench"))
    parser.add_argument("--shared-job-lock", type=Path,
                        help="flock path also used by other experiment launchers")
    sub = parser.add_subparsers(dest="action", required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("manifest", type=Path)
    sub.add_parser("probe-host")
    submit = sub.add_parser("submit")
    submit.add_argument("manifest", type=Path)
    status = sub.add_parser("status")
    status.add_argument("job_id", nargs="?")
    service = sub.add_parser("serve")
    service.add_argument("--once", action="store_true")
    direct = sub.add_parser("run")
    direct.add_argument("manifest", type=Path)
    args = parser.parse_args()
    if args.action in ("probe", "submit", "run"):
        manifest = json.loads(args.manifest.read_text()) if str(args.manifest) != "-" else json.load(sys.stdin)
        require_manifest(manifest)
    if args.action == "probe-host":
        print(json.dumps(host_probe(), indent=2, sort_keys=True))
    elif args.action == "probe":
        result = preflight(manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
        if not result["ok"]:
            raise SystemExit(3)
    elif args.action == "submit":
        db = database(args.queue_root)
        job_id = uuid.uuid4().hex
        db.execute("INSERT INTO jobs(id,status,created_ns,manifest) VALUES(?,?,?,?)",
                   (job_id, "queued", time.time_ns(), json.dumps(manifest, sort_keys=True)))
        print(job_id)
    elif args.action == "status":
        db = database(args.queue_root)
        if args.job_id:
            item = db.execute("SELECT id,status,created_ns,started_ns,finished_ns,output,summary "
                              "FROM jobs WHERE id=?", (args.job_id,)).fetchone()
            if item is None:
                raise SystemExit("unknown job id")
            record = dict(zip(("id", "status", "created_ns", "started_ns",
                               "finished_ns", "output", "summary"), item))
            if record["summary"]:
                record["summary"] = json.loads(record["summary"])
            print(json.dumps(record, default=str))
        else:
            for item in db.execute("SELECT id,status,created_ns,output FROM jobs ORDER BY created_ns"):
                print(json.dumps(item))
    elif args.action == "serve":
        serve(args.queue_root, args.once, args.shared_job_lock)
    else:
        with only_worker(args.queue_root):
            with job_slot(args.shared_job_lock):
                output = args.queue_root / "results" / uuid.uuid4().hex
                summary = execute(manifest, output)
            print(json.dumps({"output": str(output), "summary": summary}, indent=2))
            if summary["status"] != "completed":
                raise SystemExit(3)


if __name__ == "__main__":
    main()
