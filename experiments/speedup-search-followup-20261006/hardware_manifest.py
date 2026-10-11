"""Machine-readable hardware and execution manifest for the benchmark records
(AGENTS.md, "Hardware and placement for empirical benchmarks").

`collect()` returns a JSON-serialisable dict read from /proc, /sys and lscpu
on Linux.  Facts the host does not expose verifiably are written as
"unknown" rather than inferred; in particular DIMM technology, speed and
channel configuration are "unknown" on a VM.  `steal_delta()` turns two
/proc/stat snapshots into the steal and total jiffies spent during a run.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys


def _read(path: str) -> str | None:
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return None


def _lscpu() -> dict:
    if not shutil.which("lscpu"):
        return {}
    try:
        out = subprocess.run(["lscpu", "-J"], capture_output=True, text=True, check=True).stdout
        data = json.loads(out)
        flat = {}

        def walk(items):
            for it in items:
                flat[it["field"].rstrip(":")] = it["data"]
                if "children" in it:
                    walk(it["children"])

        walk(data["lscpu"])
        return flat
    except Exception:
        return {}


def _cpuinfo() -> dict:
    txt = _read("/proc/cpuinfo") or ""
    first = txt.split("\n\n")[0]
    kv = {}
    for line in first.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    return kv


def _cgroup_limits() -> dict:
    out = {"version": "unknown", "cpu_max": "unknown", "memory_max": "unknown", "cpu_stat": "unknown"}
    cg = _read("/proc/self/cgroup") or ""
    m = re.search(r"^0::(.*)$", cg, re.M)
    if m:
        out["version"] = "v2"
        rel = m.group(1).strip("/")
        out["own_path"] = "/" + rel
        parts = rel.split("/") if rel else []
        candidates = [os.path.join("/sys/fs/cgroup", *parts[:i]) for i in range(len(parts), -1, -1)]
        out["deepest_visible_path"] = next((c for c in candidates if os.path.isdir(c)), "none")
        for base in candidates:
            if not os.path.isdir(base):
                continue
            cpu_max = _read(os.path.join(base, "cpu.max"))
            if cpu_max is not None and out["cpu_max"] == "unknown":
                out["cpu_max"] = cpu_max
                out["cpu_max_path"] = base
            mem_max = _read(os.path.join(base, "memory.max"))
            if mem_max is not None and out["memory_max"] == "unknown":
                out["memory_max"] = mem_max
            stat = _read(os.path.join(base, "cpu.stat"))
            if stat is not None and out["cpu_stat"] == "unknown":
                out["cpu_stat"] = dict(l.split() for l in stat.splitlines() if len(l.split()) == 2)
                out["cpu_stat_path"] = base
        if out["cpu_max"] == "unknown":
            out["cpu_max"] = "not exposed inside this namespace (any quota is set above it)"
        if out["memory_max"] == "unknown":
            out["memory_max"] = "not exposed inside this namespace (any limit is set above it)"
        for psi in ("cpu.pressure", "memory.pressure"):
            for base in candidates:
                v = _read(os.path.join(base, psi))
                if v is not None:
                    out[psi] = v.splitlines()
                    break
    else:
        out["version"] = "v1 or none"
    return out


def _caches() -> list[dict]:
    caches = []
    base = "/sys/devices/system/cpu/cpu0/cache"
    if not os.path.isdir(base):
        return caches
    for idx in sorted(os.listdir(base)):
        d = os.path.join(base, idx)
        if not idx.startswith("index"):
            continue
        caches.append(
            {
                "level": _read(os.path.join(d, "level")),
                "type": _read(os.path.join(d, "type")),
                "size": _read(os.path.join(d, "size")),
                "ways": _read(os.path.join(d, "ways_of_associativity")),
                "line_bytes": _read(os.path.join(d, "coherency_line_size")),
                "shared_cpu_list": _read(os.path.join(d, "shared_cpu_list")),
            }
        )
    return caches


def _numa() -> dict:
    nodes = sorted(n for n in os.listdir("/sys/devices/system/node") if re.fullmatch(r"node\d+", n)) if os.path.isdir("/sys/devices/system/node") else []
    info = {}
    for n in nodes:
        info[n] = {"cpulist": _read(f"/sys/devices/system/node/{n}/cpulist"), "meminfo_total_kB": None}
        mi = _read(f"/sys/devices/system/node/{n}/meminfo") or ""
        m = re.search(r"MemTotal:\s+(\d+)", mi)
        if m:
            info[n]["meminfo_total_kB"] = int(m.group(1))
    return {"nodes": info, "exposed_node_count": len(nodes)}


def _virtualization() -> dict:
    out = {"detect_virt": "unknown", "hypervisor_flag": "hypervisor" in (_cpuinfo().get("flags", "")), "container": "unknown"}
    if shutil.which("systemd-detect-virt"):
        r = subprocess.run(["systemd-detect-virt"], capture_output=True, text=True)
        out["detect_virt"] = r.stdout.strip() or r.stderr.strip() or "unknown"
        r2 = subprocess.run(["systemd-detect-virt", "--container"], capture_output=True, text=True)
        out["container"] = r2.stdout.strip() or "none"
    return out


def _microarchitecture(family: str | None, model: str | None) -> dict:
    """Decode Intel family/model when unambiguous; otherwise unknown.  Labelled as decoded from CPUID,
    never from the marketing string."""
    table = {("6", "143"): "Sapphire Rapids", ("6", "207"): "Emerald Rapids", ("6", "106"): "Ice Lake-SP", ("6", "85"): "Skylake/Cascade Lake-SP", ("6", "173"): "Granite Rapids"}
    name = table.get((family or "", model or ""))
    return {"decoded_from_cpuid_family_model": name or "unknown", "basis": "CPUID family/model lookup table in hardware_manifest.py; independent host documentation not available"}


def proc_stat_snapshot() -> dict:
    line = (_read("/proc/stat") or "").splitlines()[0].split()
    names = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice"]
    vals = [int(x) for x in line[1:1 + len(names)]]
    return dict(zip(names, vals))


def steal_delta(before: dict, after: dict) -> dict:
    total = sum(after[k] - before[k] for k in before)
    steal = after["steal"] - before["steal"]
    return {"steal_jiffies": steal, "total_jiffies": total, "steal_fraction": (steal / total) if total else None, "clk_tck": os.sysconf("SC_CLK_TCK")}


def collect() -> dict:
    ci = _cpuinfo()
    ls = _lscpu()
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else "unknown"
    load = os.getloadavg() if hasattr(os, "getloadavg") else "unknown"
    nproc = len([p for p in os.listdir("/proc") if p.isdigit()]) if os.path.isdir("/proc") else "unknown"
    return {
        "cpu": {
            "vendor": ci.get("vendor_id", ls.get("Vendor ID", "unknown")),
            "model_name_reported": ci.get("model name", ls.get("Model name", "unknown")),
            "family": ci.get("cpu family"),
            "model": ci.get("model"),
            "stepping": ci.get("stepping"),
            "microarchitecture": _microarchitecture(ci.get("cpu family"), ci.get("model")),
            "architecture": platform.machine(),
            "flags_subset": sorted(f for f in ci.get("flags", "").split() if f in {"popcnt", "avx2", "avx512f", "avx512dq", "avx512bw", "avx512vl", "pclmulqdq", "bmi2", "adx", "aes", "sha_ni", "hypervisor"}),
            "mhz_reported": ci.get("cpu MHz", "unknown"),
            "frequency_fixed": False,
        },
        "topology": {
            "logical_cpus": os.cpu_count(),
            "online_cpus": ls.get("On-line CPU(s) list", "unknown"),
            "threads_per_core": ls.get("Thread(s) per core", "unknown"),
            "cores_per_socket": ls.get("Core(s) per socket", "unknown"),
            "sockets": ls.get("Socket(s)", "unknown"),
            "caches_cpu0": _caches(),
            "lscpu_cache_summary": {k: v for k, v in ls.items() if k.endswith("cache")},
        },
        "numa": _numa(),
        "memory": {
            "mem_total_kB": int((re.search(r"MemTotal:\s+(\d+)", _read("/proc/meminfo") or "") or [None, "0"])[1]),
            "dimm_technology": "unknown",
            "dimm_speed": "unknown",
            "channel_configuration": "unknown",
            "note": "VM: no verifiable DMI evidence; not inferred from the CPU model",
        },
        "os": {"kernel": platform.release(), "platform": platform.platform(), "python": sys.version.split()[0]},
        "virtualization": _virtualization(),
        "cgroup": _cgroup_limits(),
        "placement": {
            "allowed_cpus_sched_getaffinity": affinity,
            "selected_affinity": "none (inherited mask; CPU affinity does not reserve a core)",
            "memory_policy": "default (single exposed node; no NUMA locality claim)",
            "page_placement_observed": "not measured",
            "host_level_isolation": False,
            "isolation_receipt": None,
        },
        "co_runners_at_collection": {"loadavg_1_5_15": load, "process_count": nproc},
        "throttling": {"cgroup_cpu_stat": _cgroup_limits().get("cpu_stat", "unknown"), "thermal": "not observable in this VM"},
    }


if __name__ == "__main__":
    print(json.dumps(collect(), indent=1))
