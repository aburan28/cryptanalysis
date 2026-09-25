#!/usr/bin/env python3
"""gpu_health.py - is this node's GPU fit to run work?  A 60-120 s check.

Runs `ec2k-gpu health` (the ECC2K-130 Pollard rho walk, ecc2k130/ in this
repository) on every visible GPU at once, samples nvidia-smi while it runs,
and prints one verdict:

  correctness  every distinguished point a GPU reports is checked on the host
               (on the curve, weight, restart counter, step window) and a
               sample is re-walked on the golden model; one bad point fails it
  throughput   steady complete iterations per second against a calibrated
               baseline for this GPU model and build, against the other GPUs
               of the same model in the node, and across the run's windows
  telemetry    hardware slowdown or power-brake events, thermal throttling,
               ECC errors during the run, pending or failed row remapping, a
               PCIe link narrower than the GPU's, other processes on the GPU

Exit status: 0 pass, 1 fail, 2 the check itself could not run as asked.  The
JSON report goes to stdout (and --json-out); a one-line verdict goes to
--termination-log, which Kubernetes shows as the container's termination
message.  With --node-gate it also records the verdict on its Kubernetes node
(a label and an annotation) and, on a pass, removes the taint new GPU nodes
are registered with, so that nothing schedules onto a node until its GPUs
have passed.  See README.md beside this file for what the check does and does not
establish, and for calibrating baselines.

Python 3.8+, standard library only.
"""

import argparse
import hashlib
import json
import os
import re
import signal
import socket
import ssl
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

TOOL_VERSION = "1"

# nvmlClocksEventReasons: why the SM clock sits below its maximum.
REASONS = {
    0x1: "gpu_idle",
    0x2: "applications_clocks_setting",
    0x4: "sw_power_cap",
    0x8: "hw_slowdown",
    0x10: "sync_boost",
    0x20: "sw_thermal_slowdown",
    0x40: "hw_thermal_slowdown",
    0x80: "hw_power_brake_slowdown",
    0x100: "display_clock_setting",
}
# Hardware protection: the board or the chassis pulled the clock down.  A
# healthy, cooled, correctly powered GPU never asserts these under this load.
FAIL_REASONS = {"hw_slowdown", "hw_thermal_slowdown", "hw_power_brake_slowdown"}
# The GPU reached its temperature target; the cooling is marginal.
WARN_REASONS = {"sw_thermal_slowdown"}

STATIC_FIELDS = [
    "index", "uuid", "name", "pci.bus_id", "driver_version", "vbios_version", "serial",
    "persistence_mode", "compute_mode", "mig.mode.current", "ecc.mode.current",
    "power.limit", "enforced.power.limit", "power.max_limit", "clocks.max.sm",
    "clocks.max.memory", "pcie.link.gen.max", "pcie.link.width.max",
    "ecc.errors.corrected.volatile.total", "ecc.errors.uncorrected.volatile.total",
    "ecc.errors.uncorrected.aggregate.total", "retired_pages.pending", "temperature.gpu",
]
SAMPLE_FIELDS = [
    "uuid", "temperature.gpu", "temperature.memory", "power.draw", "clocks.sm", "clocks.mem",
    "utilization.gpu", "clocks_event_reasons.active", "clocks_throttle_reasons.active",
    "pcie.link.gen.current", "pcie.link.width.current",
    "ecc.errors.corrected.volatile.total", "ecc.errors.uncorrected.volatile.total",
]
REMAP_FIELDS = [
    "gpu_uuid", "remapped_rows.correctable", "remapped_rows.uncorrectable",
    "remapped_rows.pending", "remapped_rows.failure",
]

DEFAULT_THRESHOLDS = {
    # steady rate over the calibrated baseline for this model and build
    "baseline_fail": 0.90, "baseline_warn": 0.95,
    # steady rate over the median of the node's other GPUs of the same model
    "peer_fail": 0.90, "peer_warn": 0.95,
    # last rate window over the first: a card that slows as it heats
    "trend_fail": 0.85, "trend_warn": 0.95,
    # mean GPU utilisation during the load, percent
    "utilization_warn": 90.0,
}


def log(msg):
    print("[gpu-health] " + msg, file=sys.stderr, flush=True)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def available_cpus():
    """CPUs this process may use: its affinity, capped by a cgroup CPU quota."""
    try:
        n = len(os.sched_getaffinity(0))
    except AttributeError:
        n = os.cpu_count() or 1
    quota = None
    try:
        with open("/sys/fs/cgroup/cpu.max") as f:
            q, period = f.read().split()[:2]
            if q != "max":
                quota = int(q) / int(period)
    except (OSError, ValueError):
        try:
            with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f:
                q = int(f.read())
            with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f:
                period = int(f.read())
            if q > 0:
                quota = q / period
        except (OSError, ValueError):
            pass
    if quota is not None:
        n = min(n, max(1, int(quota)))
    return n


def last_json(text):
    """The last line of `text` that parses as a JSON object, or None."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---- nvidia-smi ---------------------------------------------------------------


def parse_value(v):
    v = v.strip()
    if v in ("", "N/A", "[N/A]", "Not Supported", "[Not Supported]", "Unknown Error",
             "[Unknown Error]", "Insufficient Permissions", "[Insufficient Permissions]"):
        return None
    if v.lower().startswith("0x"):
        try:
            return int(v, 16)
        except ValueError:
            return v
    try:
        f = float(v)
        return int(f) if f.is_integer() and "." not in v else f
    except ValueError:
        return v


def truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return isinstance(v, str) and v.strip().lower() in ("yes", "true", "enabled", "active")


class Smi:
    """nvidia-smi --query-*, asking only for fields this driver knows."""

    def __init__(self, exe, timeout=30):
        self.exe = exe
        self.timeout = timeout
        self.gpu_fields = self._supported("--help-query-gpu")
        self.remap_fields = self._supported("--help-query-remapped-rows")

    def _run(self, args):
        return subprocess.run([self.exe] + args, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True,
                              timeout=self.timeout)

    def _supported(self, flag):
        try:
            out = self._run([flag]).stdout
        except (OSError, subprocess.SubprocessError):
            return set()
        names = set()
        for line in out.splitlines():
            if line.startswith('"'):
                names.update(re.findall(r'"([A-Za-z0-9_.]+)"', line))
        return names

    def _query(self, flag, wanted, known):
        fields = [f for f in wanted if f in known]
        if not fields:
            return []
        try:
            r = self._run(["--%s=%s" % (flag, ",".join(fields)), "--format=csv,noheader,nounits"])
        except (OSError, subprocess.SubprocessError):
            return []
        if r.returncode != 0:
            return []
        rows = []
        for line in r.stdout.splitlines():
            vals = [v.strip() for v in line.split(",")]
            if len(vals) == len(fields):
                rows.append({f: parse_value(v) for f, v in zip(fields, vals)})
        return rows

    def gpus(self, fields):
        return self._query("query-gpu", fields, self.gpu_fields)

    def remapped_rows(self):
        return self._query("query-remapped-rows", REMAP_FIELDS, self.remap_fields)

    def compute_apps(self):
        rows = self._query("query-compute-apps", ["gpu_uuid", "pid"], {"gpu_uuid", "pid"})
        return rows


class Sampler(threading.Thread):
    """nvidia-smi every `interval` seconds, until stopped: (monotonic t, row)."""

    def __init__(self, smi, interval):
        super().__init__(daemon=True)
        self.smi = smi
        self.interval = interval
        self.samples = []
        self.halt = threading.Event()

    def run(self):
        while not self.halt.is_set():
            t = time.monotonic()
            for row in self.smi.gpus(SAMPLE_FIELDS):
                self.samples.append((t, row))
            self.halt.wait(max(0.0, self.interval - (time.monotonic() - t)))

    def stop(self):
        self.halt.set()
        self.join(timeout=60)


# ---- the workload --------------------------------------------------------------


class Worker(threading.Thread):
    """One `ec2k-gpu health` process on one CUDA device."""

    def __init__(self, cmd, env, label, echo=True):
        super().__init__(daemon=True)
        self.cmd = cmd
        self.env = env
        self.label = label
        self.echo = echo
        self.proc = None
        self.lines = []
        self.err = []
        self.load_start = None
        self.load_end = None
        self.rc = None
        self.started = threading.Event()

    def run(self):
        try:
            self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         universal_newlines=True, env=self.env, bufsize=1)
        except OSError as e:
            self.err.append(str(e))
            self.rc = 127
            self.started.set()
            return
        self.started.set()
        drain = threading.Thread(target=self._drain_stderr, daemon=True)
        drain.start()
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            self.lines.append(line)
            if line.startswith("health:") and self.load_start is None:
                self.load_start = time.monotonic()
            elif line.startswith("{"):
                self.load_end = time.monotonic()
            if self.echo and not line.startswith("{"):
                print("[%s] %s" % (self.label, line), file=sys.stderr, flush=True)
        self.rc = self.proc.wait()
        drain.join(timeout=10)
        if self.load_end is None:
            self.load_end = time.monotonic()

    def _drain_stderr(self):
        for line in self.proc.stderr:
            line = line.rstrip("\n")
            self.err.append(line)
            if self.echo:
                print("[%s] %s" % (self.label, line), file=sys.stderr, flush=True)

    def signal(self, sig):
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.send_signal(sig)
            except OSError:
                pass

    def result(self):
        return last_json("\n".join(self.lines))


# ---- verdicts -------------------------------------------------------------------


def median(values):
    return statistics.median(values) if values else None


def summarize_telemetry(rows):
    """Reduce a GPU's samples during the load to what the verdict reads."""
    def series(field):
        return [r[field] for r in rows if isinstance(r.get(field), (int, float))]

    reasons = set()
    for r in rows:
        mask = r.get("clocks_event_reasons.active")
        if not isinstance(mask, int):
            mask = r.get("clocks_throttle_reasons.active")
        if isinstance(mask, int):
            reasons.update(name for bit, name in REASONS.items() if mask & bit)
    out = {"samples": len(rows), "reasons": sorted(reasons)}
    for key, field, fn in [
        ("temperatureMaxC", "temperature.gpu", max),
        ("memoryTemperatureMaxC", "temperature.memory", max),
        ("powerMeanW", "power.draw", statistics.mean),
        ("powerMaxW", "power.draw", max),
        ("smClockMeanMHz", "clocks.sm", statistics.mean),
        ("smClockMinMHz", "clocks.sm", min),
        ("utilizationMeanPct", "utilization.gpu", statistics.mean),
        ("pcieWidthMax", "pcie.link.width.current", max),
        ("pcieGenMax", "pcie.link.gen.current", max),
    ]:
        s = series(field)
        out[key] = round(fn(s), 2) if s else None
    return out


def find_baseline(baselines, name, sms):
    for e in (baselines or {}).get("entries", []):
        if e.get("name") == name and e.get("sms") in (None, sms):
            return e
    return None


def evaluate(gpus, baselines, thresholds, binary_sha, calibrate=False):
    """Fill each GPU's failures, warnings and notes; return the node verdict.

    `gpus` is a list of dicts with keys: device (from `ec2k-gpu devices`),
    rc, result (the health JSON or None), stderr (list of lines), telemetry
    (summarize_telemetry or None), static (nvidia-smi row or None), post
    (nvidia-smi row after the load or None), remap (row or None), apps (other
    processes seen before the load).
    """
    t = dict(DEFAULT_THRESHOLDS)
    t.update(thresholds or {})
    for g in gpus:
        g.setdefault("failures", [])
        g.setdefault("warnings", [])
        g.setdefault("notes", [])
        check_workload(g)
        check_telemetry(g, t)
        check_memory(g)
    check_throughput(gpus, baselines, t, binary_sha, calibrate)
    for g in gpus:
        g["verdict"] = "fail" if g["failures"] else "pass"
    return "fail" if any(g["failures"] for g in gpus) or not gpus else "pass"


def check_workload(g):
    res, rc, dev = g.get("result"), g.get("rc"), g["device"]
    cc = dev.get("computeCapability", "0.0")
    try:
        major = int(str(cc).split(".")[0])
    except ValueError:
        major = 0
    if major and major < 8:
        g["failures"].append(
            "unsupported: compute capability %s; the walk's products are carry-less multiplies "
            "(clmad), which need sm_80 (Ampere) or newer" % cc)
        return
    if res is None:
        tail = " | ".join(line for line in g.get("stderr", [])[-3:] if line)
        if g.get("timedOut"):
            g["failures"].append("the load hung: no result after %.0f s and it had to be "
                                 "killed (%s)" % (g.get("timeout", 0), tail or "no output"))
        else:
            g["failures"].append("the load died without a result, exit %s (%s)" %
                                 (rc, tail or "no output"))
        return
    faults = res.get("faults", {})
    bad = {k: v for k, v in faults.items() if v}
    if bad or res.get("status") == "fault":
        g["failures"].append(
            "silent data corruption: %s of %s reports failed a check (%s)" %
            (sum(bad.values()), res.get("checked"),
             ", ".join("%s %s" % (v, k) for k, v in sorted(bad.items()))))
    elif res.get("status") != "ok":
        why = res.get("lost") or ("stopped before the end" if res.get("stopped") else
                                  "no report was checked or re-walked")
        g["failures"].append("inconclusive: %s" % why)
    if rc not in (0, None) and res.get("status") == "ok":
        g["failures"].append("the load exited %s after reporting ok" % rc)
    g["notes"].append(
        "%s reports checked (%.1f%% of the iterations), %s re-walked on the golden model" %
        (res.get("checked"), 100.0 * (res.get("checkedFraction") or 0),
         (res.get("rewalk") or {}).get("rewalked")))


def check_throughput(gpus, baselines, t, binary_sha, calibrate):
    rated = [g for g in gpus if g.get("result") and g["result"].get("steadyIterationsPerSecond")]
    for g in rated:
        res, dev = g["result"], g["device"]
        rate = res["steadyIterationsPerSecond"]
        tp = g.setdefault("throughput", {})
        tp.update({"steady": rate, "windowMinOverMax": res.get("windowMinOverMax"),
                   "windowLastOverFirst": res.get("windowLastOverFirst"),
                   "baseline": None, "baselineRatio": None, "peerRatio": None})
        trend = res.get("windowLastOverFirst")
        if trend and len(res.get("windows", [])) >= 2:
            if trend < t["trend_fail"]:
                g["failures"].append("rate fell to %.1f%% of its first window by the last: "
                                     "the GPU is slowing under load" % (100 * trend))
            elif trend < t["trend_warn"]:
                g["warnings"].append("rate fell to %.1f%% of its first window by the last" %
                                     (100 * trend))
        if calibrate:
            continue
        base = find_baseline(baselines, dev.get("name"), dev.get("sms"))
        if base is None:
            g["notes"].append("no baseline for %s (%s SMs): throughput not rated against one; "
                              "calibrate one with --calibrate" % (dev.get("name"), dev.get("sms")))
        else:
            ratio = rate / float(base["iterationsPerSecond"])
            tp["baseline"], tp["baselineRatio"] = base["iterationsPerSecond"], round(ratio, 4)
            other_build = base.get("binarySha256") not in (None, binary_sha)
            msg = "steady rate %.3g it/s is %.1f%% of the %s baseline %.3g" % (
                rate, 100 * ratio, dev.get("name"), base["iterationsPerSecond"])
            if other_build:
                g["warnings"].append("the baseline was measured with another ec2k-gpu build; "
                                     "its comparison is advisory")
            if ratio < t["baseline_fail"] and not other_build:
                g["failures"].append(msg)
            elif ratio < t["baseline_warn"]:
                g["warnings"].append(msg)
    # Peers: the same model in the same node should run at the same rate.
    groups = {}
    for g in rated:
        groups.setdefault((g["device"].get("name"), g["device"].get("sms")), []).append(g)
    for members in groups.values():
        if len(members) < 2:
            continue
        for g in members:
            others = [m["result"]["steadyIterationsPerSecond"] for m in members if m is not g]
            ref = median(others)
            ratio = g["result"]["steadyIterationsPerSecond"] / ref
            g["throughput"]["peerRatio"] = round(ratio, 4)
            msg = "steady rate is %.1f%% of the median of the %d other %s in this node" % (
                100 * ratio, len(others), g["device"].get("name"))
            if ratio < t["peer_fail"]:
                g["failures"].append(msg)
            elif ratio < t["peer_warn"]:
                g["warnings"].append(msg)


def check_telemetry(g, t):
    tel, static = g.get("telemetry"), g.get("static") or {}
    if not tel or not tel.get("samples"):
        g["notes"].append("no nvidia-smi samples during the load: clocks, power, temperature "
                          "and throttling not checked")
        return
    reasons = set(tel.get("reasons", []))
    hw = sorted(reasons & FAIL_REASONS)
    if hw:
        g["failures"].append("hardware clock slowdown during the load: %s" % ", ".join(hw))
    sw = sorted(reasons & WARN_REASONS)
    if sw:
        g["warnings"].append("thermal throttling during the load: %s (max %s C)" %
                             (", ".join(sw), tel.get("temperatureMaxC")))
    util = tel.get("utilizationMeanPct")
    if util is not None and util < t["utilization_warn"]:
        g["warnings"].append("GPU utilisation averaged %.0f%% during the load" % util)
    wmax, wcur = static.get("pcie.link.width.max"), tel.get("pcieWidthMax")
    if isinstance(wmax, (int, float)) and isinstance(wcur, (int, float)) and wcur < wmax:
        g["warnings"].append("PCIe link x%d, narrower than the GPU's x%d" % (wcur, wmax))
    if g.get("apps"):
        g["warnings"].append("%d other process(es) were using the GPU before the load" %
                             len(g["apps"]))
    limit = static.get("enforced.power.limit") or static.get("power.limit")
    power = tel.get("powerMeanW")
    clock_max = static.get("clocks.max.sm")
    note = "load: %s C max, %s W mean" % (tel.get("temperatureMaxC"), power)
    if isinstance(limit, (int, float)) and isinstance(power, (int, float)) and limit:
        note += " of %s W (%.0f%%)" % (limit, 100.0 * power / limit)
    note += ", SM clock %s MHz mean of %s max" % (tel.get("smClockMeanMHz"), clock_max)
    if reasons:
        note += ", clock event reasons: %s" % ", ".join(sorted(reasons))
    g["notes"].append(note)


def check_memory(g):
    static, post, remap = g.get("static") or {}, g.get("post") or {}, g.get("remap") or {}
    before = static.get("ecc.errors.uncorrected.volatile.total")
    after = post.get("ecc.errors.uncorrected.volatile.total")
    if isinstance(after, int) and isinstance(before, int) and after > before:
        g["failures"].append("%d uncorrectable ECC error(s) during the load" % (after - before))
    elif isinstance(before, int) and before > 0:
        g["failures"].append("%d uncorrectable ECC error(s) since the driver loaded" % before)
    cb = static.get("ecc.errors.corrected.volatile.total")
    ca = post.get("ecc.errors.corrected.volatile.total")
    if isinstance(ca, int) and isinstance(cb, int) and ca > cb:
        g["warnings"].append("%d correctable ECC error(s) during the load" % (ca - cb))
    if truthy(remap.get("remapped_rows.failure")):
        g["failures"].append("row remapping has failed: the GPU's memory needs service")
    if truthy(remap.get("remapped_rows.pending")):
        g["failures"].append("a row remap is pending: the GPU needs a reset before use")
    if truthy(static.get("retired_pages.pending")):
        g["failures"].append("a page retirement is pending: the GPU needs a reset before use")
    if truthy(static.get("mig.mode.current")):
        g["warnings"].append("MIG is enabled: this check measures a MIG slice, and baselines "
                             "are for whole GPUs")


def calibration(gpus, binary_sha, driver):
    groups = {}
    for g in gpus:
        res = g.get("result") or {}
        if g.get("failures") or not res.get("steadyIterationsPerSecond"):
            continue
        key = (g["device"].get("name"), g["device"].get("sms"))
        groups.setdefault(key, []).append((res["steadyIterationsPerSecond"], g))
    entries = []
    for (name, sms), members in sorted(groups.items(), key=lambda kv: str(kv[0])):
        rates = [r for r, _ in members]
        static = members[0][1].get("static") or {}
        entries.append({
            "name": name, "sms": sms, "iterationsPerSecond": round(median(rates)),
            "gpus": len(rates), "min": round(min(rates)), "max": round(max(rates)),
            "powerLimitW": static.get("enforced.power.limit") or static.get("power.limit"),
            "binarySha256": binary_sha, "driverVersion": driver,
            "node": socket.gethostname(), "measuredAt": now_iso(),
        })
    return {"schema": 1, "entries": entries}


# ---- the run -------------------------------------------------------------------


def parse_args(argv):
    env = os.environ.get
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--seconds", type=float, default=float(env("GPU_HEALTH_SECONDS", "60")),
                   help="length of the load on every GPU (default 60)")
    p.add_argument("--binary", default=env("GPU_HEALTH_BINARY", "/usr/local/bin/ec2k-gpu"))
    p.add_argument("--baselines", default=env("GPU_HEALTH_BASELINES", ""),
                   help="baseline JSON (see README.md); empty: no baseline comparison")
    p.add_argument("--expect-gpus", type=int, default=int(env("GPU_HEALTH_EXPECT_GPUS", "0")),
                   help="fail unless exactly this many GPUs are visible (0: any)")
    p.add_argument("--nvidia-smi", default=env("GPU_HEALTH_NVIDIA_SMI", "nvidia-smi"))
    p.add_argument("--sample-interval", type=float, default=2.0)
    p.add_argument("--rewalk-threads", type=int, default=int(env("GPU_HEALTH_REWALK_THREADS", "0")),
                   help="golden-model re-walk threads per GPU (0: from the CPUs available)")
    p.add_argument("--kat", default=env("GPU_HEALTH_KAT", ""),
                   help="also replay the campaign's known answers (about 13 s of one core)")
    p.add_argument("--threshold", action="append", default=[], metavar="NAME=VALUE",
                   help="override a threshold: %s" % ", ".join(sorted(DEFAULT_THRESHOLDS)))
    p.add_argument("--json-out", default=env("GPU_HEALTH_JSON_OUT", ""))
    p.add_argument("--termination-log", default=env("GPU_HEALTH_TERMINATION_LOG",
                                                    "/dev/termination-log"))
    p.add_argument("--calibrate", action="store_true",
                   default=env("GPU_HEALTH_CALIBRATE", "") not in ("", "0", "false"),
                   help="measure and print baseline entries instead of rating throughput")
    p.add_argument("--strict", action="store_true",
                   default=env("GPU_HEALTH_STRICT", "") not in ("", "0", "false"),
                   help="treat warnings as failures")
    p.add_argument("--quiet", action="store_true", help="do not echo the workload's output")
    p.add_argument("--setup-allowance", type=float, default=120.0,
                   help="seconds a GPU may take beyond --seconds before it counts as hung")
    p.add_argument("--kill-grace", type=float, default=20.0,
                   help="seconds between SIGTERM and SIGKILL for a hung load")
    p.add_argument("--node-gate", action="store_true",
                   default=env("GPU_HEALTH_NODE_GATE", "") not in ("", "0", "false"),
                   help="label NODE_NAME with the verdict and, on a pass, remove --gate-taint "
                        "(in-cluster service account; see k8s/node-gate.yaml)")
    p.add_argument("--gate-taint", default=env("GPU_HEALTH_GATE_TAINT", "gpu-health/pending"))
    p.add_argument("--gate-label", default=env("GPU_HEALTH_GATE_LABEL", "gpu-health/verdict"))
    a = p.parse_args(argv)
    a.thresholds = {}
    for item in a.threshold:
        name, _, value = item.partition("=")
        if name not in DEFAULT_THRESHOLDS:
            p.error("unknown threshold %s" % name)
        a.thresholds[name] = float(value)
    if not a.seconds > 0:
        p.error("--seconds must be positive")
    return a


def write_termination_log(path, text):
    if not path:
        return
    try:
        with open(path, "w") as f:
            f.write(text[:4000])
    except OSError:
        pass


def run(a):
    started = now_iso()
    report = {"tool": "gpu-health", "version": TOOL_VERSION, "startedAt": started,
              "node": os.environ.get("NODE_NAME") or socket.gethostname(),
              "seconds": a.seconds, "verdict": "fail", "gpus": [], "errors": [],
              "warnings": []}
    if not (os.path.isfile(a.binary) and os.access(a.binary, os.X_OK)):
        report["errors"].append("no workload binary at %s" % a.binary)
        return report, 2
    baselines = load_baselines(a.baselines)
    binary_sha = sha256_of(a.binary)
    report["binary"] = {"path": a.binary, "sha256": binary_sha}
    env = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID")

    # The host's own arithmetic first: the checks below run on it.
    check = [a.binary, "check", "--rounds", "16"] + (["--kat", a.kat] if a.kat else [])
    r = subprocess.run(check, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, timeout=300, env=env)
    report["hostCheck"] = last_json(r.stdout)
    if r.returncode != 0:
        report["errors"].append("the host's arithmetic self-check failed: %s" %
                                (r.stderr.strip().splitlines() or ["?"])[-1])
        return report, 1

    r = subprocess.run([a.binary, "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, timeout=120, env=env)
    devs = last_json(r.stdout) or {}
    report["cuda"] = {k: devs.get(k) for k in ("driverVersion", "runtimeVersion", "error")}
    devices = devs.get("devices") or []
    if r.returncode != 0 or not devices:
        report["errors"].append("no usable CUDA device: %s" %
                                (devs.get("error") or r.stderr.strip() or "none visible"))
        return report, 1
    if a.expect_gpus and len(devices) != a.expect_gpus:
        report["errors"].append("%d GPU(s) visible, %d expected" % (len(devices), a.expect_gpus))
        return report, 1

    smi = None
    if a.nvidia_smi and (os.path.sep in a.nvidia_smi and os.access(a.nvidia_smi, os.X_OK)
                         or any(os.access(os.path.join(d, a.nvidia_smi), os.X_OK)
                                for d in os.environ.get("PATH", "").split(os.pathsep) if d)):
        smi = Smi(a.nvidia_smi)
        if not smi.gpu_fields:
            smi = None
    if smi is None:
        report["warnings"].append("nvidia-smi unavailable (set NVIDIA_DRIVER_CAPABILITIES to "
                                "include utility): telemetry checks skipped")
    static = {row.get("uuid"): row for row in (smi.gpus(STATIC_FIELDS) if smi else [])}
    remap = {row.get("gpu_uuid"): row for row in (smi.remapped_rows() if smi else [])}
    apps = {}
    for row in (smi.compute_apps() if smi else []):
        apps.setdefault(row.get("gpu_uuid"), []).append(row)
    driver = next((s.get("driver_version") for s in static.values()), None)
    report["driverVersion"] = driver

    cpus = available_cpus()
    threads = a.rewalk_threads or max(1, min(4, (cpus - len(devices)) // len(devices)))
    report["cpus"] = cpus
    if cpus < len(devices):
        report["warnings"].append("%d CPU(s) for %d GPUs: the host checks may hold the GPUs "
                                "back; give the check a CPU per GPU" % (cpus, len(devices)))
    sampler = None
    if smi:
        sampler = Sampler(smi, a.sample_interval)
        sampler.start()
    workers = []
    for d in devices:
        cmd = [a.binary, "health", "--device", str(d["index"]), "--seconds", "%g" % a.seconds,
               "--rewalk-threads", str(threads)]
        workers.append(Worker(cmd, env, "gpu%d" % d["index"], echo=not a.quiet))
    log("%d GPU(s): %s; %g s of load each, %d re-walk thread(s) per GPU" % (
        len(devices), ", ".join(sorted({d["name"] for d in devices})), a.seconds, threads))

    stop = {"sig": None}

    def forward(sig, _frame):
        stop["sig"] = sig
        for w in workers:
            w.signal(signal.SIGTERM)

    old = {s: signal.signal(s, forward) for s in (signal.SIGTERM, signal.SIGINT)}
    for w in workers:
        w.start()
    timeout = a.seconds + max(a.setup_allowance, a.seconds)
    deadline = time.monotonic() + timeout
    for w in workers:
        w.join(timeout=max(0.0, deadline - time.monotonic()))
    hung = [w for w in workers if w.is_alive()]
    for w in hung:
        w.signal(signal.SIGTERM)
    for w in hung:
        w.join(timeout=a.kill_grace)
        if w.is_alive():
            w.signal(signal.SIGKILL)
            w.join(timeout=10)
    for s, h in old.items():
        signal.signal(s, h)
    if sampler:
        sampler.stop()
    post = {row.get("uuid"): row for row in (smi.gpus(STATIC_FIELDS) if smi else [])}
    if smi:
        remap_after = {row.get("gpu_uuid"): row for row in smi.remapped_rows()}
        for k, v in remap_after.items():
            remap[k] = v

    gpus = []
    for d, w in zip(devices, workers):
        uuid = d.get("uuid")
        g = {"device": d, "rc": w.rc, "result": w.result(), "stderr": w.err[-20:],
             "timedOut": w in hung, "timeout": timeout, "static": static.get(uuid),
             "post": post.get(uuid), "remap": remap.get(uuid), "apps": apps.get(uuid, [])}
        if sampler and w.load_start is not None:
            begin = w.load_start + ((g["result"] or {}).get("warmupSeconds") or 0)
            rows = [row for (ts, row) in sampler.samples
                    if row.get("uuid") == uuid and w.load_start <= ts <= w.load_end]
            steady = [row for (ts, row) in sampler.samples
                      if row.get("uuid") == uuid and begin <= ts <= w.load_end]
            g["telemetry"] = summarize_telemetry(steady or rows)
            # Throttle events count whenever they happened under load.
            g["telemetry"]["reasons"] = summarize_telemetry(rows)["reasons"]
        gpus.append(g)
    verdict = evaluate(gpus, baselines, a.thresholds, binary_sha, a.calibrate)
    if stop["sig"] is not None:
        report["errors"].append("interrupted by signal %d: the check did not finish" % stop["sig"])
        verdict = "fail"
    if a.strict:
        for g in gpus:
            g["failures"].extend("(strict) " + w for w in g["warnings"])
            g["verdict"] = "fail" if g["failures"] else "pass"
        report["errors"].extend("(strict) " + w for w in report["warnings"])
        if report["errors"] or any(g["failures"] for g in gpus):
            verdict = "fail"
    report["verdict"] = verdict
    report["finishedAt"] = now_iso()
    for g in gpus:
        if g["verdict"] == "pass":
            g.pop("stderr", None)
        report["gpus"].append(g)
    if a.calibrate:
        report["calibration"] = calibration(gpus, binary_sha, driver)
    return report, 0 if verdict == "pass" else 1


# ---- the node gate ---------------------------------------------------------------

SA = "/var/run/secrets/kubernetes.io/serviceaccount"


def kube_api(method, path, body=None, content_type="application/json"):
    """One request to the API server with the pod's service account."""
    host = os.environ["KUBERNETES_SERVICE_HOST"]
    port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
    if ":" in host:
        host = "[%s]" % host
    with open(os.path.join(SA, "token")) as f:
        token = f.read().strip()
    ctx = ssl.create_default_context(cafile=os.path.join(SA, "ca.crt"))
    req = urllib.request.Request("https://%s:%s%s" % (host, port, path), method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + token,
                                          "Content-Type": content_type,
                                          "Accept": "application/json"})
    # The API server is in-cluster: never through a proxy from the environment.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                         urllib.request.HTTPSHandler(context=ctx))
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"message": e.read().decode(errors="replace")[:500]}


def gate_node(node, verdict, summary, taint_key, label_key, api=kube_api):
    """Record the verdict on the node; on a pass, lift the taint.  Returns an
    error string, or None.  The patch carries the node's resourceVersion, so a
    concurrent change to its taints makes it fail with 409 and it is retried
    against the new list rather than overwriting it."""
    path = "/api/v1/nodes/" + node
    for _ in range(5):
        code, obj = api("GET", path)
        if code != 200:
            return "reading node %s: HTTP %s %s" % (node, code, obj.get("message", ""))
        meta, spec = obj.get("metadata", {}), obj.get("spec", {})
        patch = {"metadata": {"resourceVersion": meta.get("resourceVersion"),
                              "labels": {label_key: verdict},
                              "annotations": {label_key: "%s %s" % (now_iso(), summary[:900])}}}
        taints = spec.get("taints") or []
        kept = [t for t in taints if t.get("key") != taint_key]
        if verdict == "pass" and len(kept) != len(taints):
            patch["spec"] = {"taints": kept or None}
        code, obj = api("PATCH", path, patch, "application/merge-patch+json")
        if code == 200:
            return None
        if code != 409:
            return "patching node %s: HTTP %s %s" % (node, code, obj.get("message", ""))
    return "patching node %s: still conflicting after 5 attempts" % node


def load_baselines(path):
    if not path:
        return None
    with open(path) as f:
        return json.load(f)


def one_line(report):
    gpus = report.get("gpus", [])
    head = "%s %d/%d GPU(s) healthy on %s" % (
        report["verdict"].upper(), sum(g.get("verdict") == "pass" for g in gpus), len(gpus),
        report.get("node"))
    parts = [head] + report.get("errors", []) + report.get("warnings", [])
    for g in gpus:
        d = g["device"]
        for f in g.get("failures", []):
            parts.append("gpu%s %s %s: %s" % (d.get("index"), d.get("uuid"), d.get("name"), f))
    rates = [g["result"]["steadyIterationsPerSecond"] for g in gpus
             if g.get("result") and g["result"].get("steadyIterationsPerSecond")]
    if rates:
        parts.append("median steady rate %.4g it/s" % median(rates))
    return "; ".join(parts)


def print_table(report):
    for g in report.get("gpus", []):
        d, tp = g["device"], g.get("throughput") or {}
        log("gpu%s %s %s (%s SMs): %s, steady %s it/s, baseline x%s, peers x%s" % (
            d.get("index"), d.get("name"), d.get("uuid"), d.get("sms"), g["verdict"].upper(),
            "%.4g" % tp["steady"] if tp.get("steady") else "-",
            tp.get("baselineRatio") or "-", tp.get("peerRatio") or "-"))
        for kind in ("failures", "warnings", "notes"):
            for line in g.get(kind, []):
                log("    %s: %s" % (kind[:-1] if kind != "notes" else "note", line))
    for e in report.get("errors", []):
        log("error: " + e)
    for w in report.get("warnings", []):
        log("warning: " + w)


def gate_pending(a, api=kube_api):
    """In --node-gate mode: None when the node still carries the gate taint
    (check it), else the one-line reason not to.  A node without the taint has
    been released and may be running work: loading its GPUs now would disturb
    that work and measure it rather than the GPUs."""
    node = os.environ.get("NODE_NAME", "")
    if not node:
        return "NODE_NAME is not set (downward API spec.nodeName); not checking", 2
    try:
        code, obj = api("GET", "/api/v1/nodes/" + node)
    except (OSError, KeyError, ValueError) as e:
        return "reading node %s from the Kubernetes API: %s" % (node, e), 1
    if code != 200:
        return "reading node %s: HTTP %s %s" % (node, code, obj.get("message", "")), 1
    if any(t.get("key") == a.gate_taint for t in (obj.get("spec", {}).get("taints") or [])):
        return None, 0
    return ("SKIP node %s has no %s taint: it was released already, so its GPUs are not "
            "loaded again; taint it and recreate this pod to re-check" % (node, a.gate_taint)), 0


def main(argv=None, api=kube_api):
    a = parse_args(sys.argv[1:] if argv is None else argv)
    if a.node_gate:
        skip, rc = gate_pending(a, api)
        if skip is not None:
            log(skip)
            write_termination_log(a.termination_log, skip)
            return rc
    try:
        report, rc = run(a)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        report = {"tool": "gpu-health", "verdict": "fail", "errors": [str(e)], "gpus": []}
        rc = 2
    if rc == 2:
        report["verdict"] = "error"
    print_table(report)
    text = json.dumps(report, sort_keys=True)
    print(text, flush=True)
    if a.json_out:
        with open(a.json_out, "w") as f:
            json.dump(report, f, indent=2, sort_keys=True)
    if a.calibrate and "calibration" in report:
        log("baseline entries (merge into your baselines file):")
        print(json.dumps(report["calibration"], indent=2, sort_keys=True), file=sys.stderr)
    verdict = one_line(report)
    if a.node_gate:
        node, result = os.environ["NODE_NAME"], "pass" if rc == 0 else "fail"
        try:
            why = gate_node(node, result, verdict, a.gate_taint, a.gate_label, api=api)
        except (OSError, KeyError, ValueError) as e:
            why = "the Kubernetes API: %s" % e
        if why:
            log("node gate: " + why)
            verdict += "; node gate failed: " + why
            rc = rc or 1
        else:
            log("node gate: %s labelled %s=%s%s" % (node, a.gate_label, result,
                                                   ", %s lifted" % a.gate_taint if rc == 0 else ""))
    # Last, so that a termination message taken from the log's tail
    # (terminationMessagePolicy: FallbackToLogsOnError) ends with the verdict.
    log(verdict)
    write_termination_log(a.termination_log, verdict)
    return rc


if __name__ == "__main__":
    sys.exit(main())
