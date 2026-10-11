"""Matched 120-second all-eight-mask positive solver control."""

import gzip
import hashlib
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

import run as short

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "long_pin8_protocol.json"
RESULT = HERE / "long_pin8_result.json"
SOLVER_CAP = 120
PARENT_CAP = 125
RSS_CAP = 4 * 1024**3


def freeze():
    if PROTOCOL.exists():
        raise FileExistsError(PROTOCOL)
    f = short.guarded.fixture()
    p = json.loads((HERE / "protocol.json").read_text())
    assert p["known_masks"] == f["known_masks"]
    value = {"status": "FROZEN_GUARDED_N41_W9_LONG_PIN8_CONTROL",
             "candidate_id": None,
             "public_target_original": f["public_target_original"],
             "raw_target_preimage_z": f["raw_target_reciprocals"],
             "known_masks": f["known_masks"],
             "pinned_source_masks": 8,
             "solver_cap_seconds": SOLVER_CAP,
             "parent_cap_seconds": PARENT_CAP,
             "rss_cap_bytes": RSS_CAP,
             "workers": 1,
             "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                              "--random=20261011", "--maxtime=120"],
             "source_sha256": {**{key: short.sha(path) for key, path in short.files().items()},
                               "long_runner": short.sha(Path(__file__)),
                               "short_protocol": short.sha(HERE / "protocol.json")}}
    short.save(PROTOCOL, value)
    print(value["status"])


def execute():
    if RESULT.exists():
        raise FileExistsError(RESULT)
    p = json.loads(PROTOCOL.read_text())
    assert p["source_sha256"]["long_runner"] == short.sha(Path(__file__))
    assert p["source_sha256"]["short_protocol"] == short.sha(HERE / "protocol.json")
    f = short.guarded.fixture()
    began = time.monotonic()
    circuit, metadata, construction_seconds = short.guarded.old.build(
        f["raw_target_reciprocals"])
    for wires, mask in zip(metadata["masks"], f["known_masks"]):
        circuit.clauses.extend(
            f"{wire if mask >> bit & 1 else -wire} 0"
            for bit, wire in enumerate(wires))
    assert len(circuit.clauses) == 27302 + 72
    with tempfile.NamedTemporaryFile(prefix="n41_long_pin8_", suffix=".xcnf",
                                     dir="/private/tmp", delete=False) as stream:
        formula = Path(stream.name)
    try:
        circuit.write(formula)
        formula_hash = short.sha(formula)
        formula_bytes = formula.stat().st_size
        with tempfile.NamedTemporaryFile(dir="/private/tmp") as stdout_file, \
             tempfile.NamedTemporaryFile(dir="/private/tmp") as stderr_file:
            solver_start = time.monotonic()
            proc = subprocess.Popen([str(short.SOLVER), *p["solver_flags"], str(formula)],
                                    stdout=stdout_file, stderr=stderr_file)
            child, parent = psutil.Process(proc.pid), psutil.Process()
            peak = 0
            timed_out = memory_exceeded = False
            while proc.poll() is None:
                try:
                    rss = child.memory_info().rss + parent.memory_info().rss
                except psutil.NoSuchProcess:
                    rss = parent.memory_info().rss
                peak = max(peak, rss)
                if rss > RSS_CAP:
                    memory_exceeded = True
                    proc.kill()
                    break
                if time.monotonic() - solver_start > PARENT_CAP:
                    timed_out = True
                    proc.kill()
                    break
                time.sleep(0.2)
            returncode = proc.wait()
            stdout_file.flush()
            stderr_file.flush()
            stdout = Path(stdout_file.name).read_bytes()
            stderr = Path(stderr_file.name).read_bytes()
        solver_seconds = time.monotonic() - solver_start
        with gzip.open(HERE / "long_pin8.stdout.gz", "wb") as stream:
            stream.write(stdout)
        with gzip.open(HERE / "long_pin8.stderr.gz", "wb") as stream:
            stream.write(stderr)
        status = ("RESOURCE_GATE_EXCEEDED" if memory_exceeded else
                  "SAT_PENDING_GROUP_REPLAY" if b"s SATISFIABLE" in stdout else
                  "UNSAT" if b"s UNSATISFIABLE" in stdout else
                  "BOUNDED_UNKNOWN")
        result = {"status": status, "candidate_id": None,
                  "solver_started": True,
                  "solver_timed_out": timed_out,
                  "solver_rss_exceeded": memory_exceeded,
                  "solver_returncode": returncode,
                  "solver_seconds": solver_seconds,
                  "construction_seconds": construction_seconds,
                  "total_wall_seconds": time.monotonic() - began,
                  "peak_combined_rss_bytes": peak,
                  "peak_self_ru_maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "formula_clauses": len(circuit.clauses),
                  "formula_bytes": formula_bytes,
                  "formula_sha256": formula_hash,
                  "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                  "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                  "active_restart_lines": sum(line.startswith(b"c rst")
                                              for line in stdout.splitlines()),
                  "protocol_sha256": short.sha(PROTOCOL),
                  "source_sha256": short.sha(Path(__file__))}
        short.save(RESULT, result)
        print(result["status"], result["solver_seconds"],
              result["active_restart_lines"])
    finally:
        formula.unlink(missing_ok=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["freeze"]:
        freeze()
    elif sys.argv[1:] == ["run"]:
        execute()
    else:
        raise SystemExit("usage: run_long.py freeze|run")
