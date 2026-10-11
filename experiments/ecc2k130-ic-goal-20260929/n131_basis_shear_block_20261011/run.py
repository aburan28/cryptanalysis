"""Freeze and bound one source-bound N131 W15 quartic block construction."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASIS = ROOT / "n41_basis_shear_20261011"
NORM = ROOT / "n41_quartic_joint_public_20261010" / "norm_result.json"
CONTROL = ROOT / "n41_quartic_joint_public_20261010" / "audit_result.json"
WITNESS = ROOT / "n131_w15_joint_block_resultant_20261010" / "restricted_result.json"
CAP_SECONDS = 120
RSS_CAP = 4 * 1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, result):
    Path(path).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


def sources():
    return {"run.py": HERE / "run.py", "worker.py": HERE / "worker.py",
            "basis_circuit.py": BASIS / "circuit.py",
            "basis_sparse.py": BASIS / "sparse.py",
            "karatsuba_circuit.py": ROOT.parent / "koblitz-polynomial-w-pair-20260925" /
                                    "karatsuba_circuit.py",
            "circuit_sat.py": ROOT.parent / "koblitz-s5-invariant-20260924" /
                              "circuit_sat.py",
            "norm_result.json": NORM, "audit_result.json": CONTROL,
            "restricted_result.json": WITNESS}


def freeze():
    paths = sources()
    record = {"status": "FROZEN_BEFORE_N131_BLOCK_CONSTRUCTION",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "field": "GF(2)[t]/(t^131+t^13+t^2+t+1)",
              "source": "W15 four raw atoms; rotations 26,39; four masks and two outputs free",
              "control_masks": [5576, 8382, 3, 13685],
              "target_count": 0, "workers": 1,
              "parent_wall_cap_seconds": CAP_SECONDS,
              "combined_rss_cap_bytes": RSS_CAP,
              "python": sys.executable,
              "source_paths": {key: str(path) for key, path in paths.items()},
              "source_sha256": {key: sha(path) for key, path in paths.items()}}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"], "cap_seconds": CAP_SECONDS}))


def execute():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_N131_BLOCK_CONSTRUCTION"
    assert protocol["source_sha256"] == {key: sha(path) for key, path in sources().items()}
    stdout_path = HERE / "worker.stdout.txt"
    stderr_path = HERE / "worker.stderr.txt"
    start = time.monotonic()
    with stdout_path.open("w") as out, stderr_path.open("w") as err:
        process = subprocess.Popen([sys.executable, "-B", str(HERE / "worker.py")],
                                   stdout=out, stderr=err, cwd=HERE)
        child = psutil.Process(process.pid)
        timed_out = rss_exceeded = False
        peak_rss = 0
        while process.poll() is None:
            try:
                peak_rss = max(peak_rss, child.memory_info().rss)
            except psutil.NoSuchProcess:
                break
            if peak_rss > RSS_CAP:
                rss_exceeded = True
                process.kill()
                break
            if time.monotonic() - start > CAP_SECONDS:
                timed_out = True
                process.kill()
                break
            time.sleep(0.1)
        returncode = process.wait()
    elapsed = time.monotonic() - start
    child_record = json.loads((HERE / "worker_result.json").read_text()) if (
        returncode == 0 and (HERE / "worker_result.json").exists()) else None
    status = ("RESOURCE_GATE_EXCEEDED" if rss_exceeded else
              "BOUNDED_UNKNOWN" if timed_out else
              child_record["status"] if child_record else "PRODUCER_FAILURE")
    record = {"status": status, "worker_returncode": returncode,
              "worker_started": True, "worker_timed_out": timed_out,
              "worker_rss_exceeded": rss_exceeded,
              "parent_wall_seconds": elapsed, "sampled_peak_rss_bytes": peak_rss,
              "worker_record_sha256": sha(HERE / "worker_result.json") if child_record else None,
              "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
              "protocol_sha256": sha(HERE / "protocol.json")}
    save(HERE / "run_result.json", record)
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "execute"))
    {"freeze": freeze, "execute": execute}[parser.parse_args().mode]()
