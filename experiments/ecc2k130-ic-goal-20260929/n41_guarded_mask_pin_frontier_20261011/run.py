"""Frozen source-mask pin frontier on the guarded W9 public-point formula."""

import gzip
import hashlib
import importlib.util
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GUARDED = HERE.parent / "n41_branchfree_s3_20261011/guarded"
W9 = HERE.parent / "n41_w7_entropy_cubic_20261011/w9"
sys.path.insert(0, str(GUARDED))
spec = importlib.util.spec_from_file_location("guarded_runner", GUARDED / "run.py")
guarded = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guarded)
SOLVER = guarded.old.SOLVER
CAP = 20
PARENT_CAP = 25
RSS_CAP = 4 * 1024**3
PIN_COUNTS = [8, 6, 4, 2, 1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def files():
    return {"runner": Path(__file__), "guarded_runner": GUARDED / "run.py",
            "guarded_circuit": GUARDED / "circuit.py",
            "guarded_public_protocol": GUARDED / "query/protocol.json",
            "guarded_full_control": GUARDED / "full_assignment.json",
            "w9_fixture": W9 / "fixture.json", "solver": SOLVER}


def freeze():
    path = HERE / "protocol.json"
    if path.exists():
        raise FileExistsError(path)
    f = guarded.fixture()
    q = json.loads((GUARDED / "query/protocol.json").read_text())
    assert q["public_target_original"] == f["public_target_original"]
    record = {"status": "FROZEN_GUARDED_N41_W9_MASK_PIN_FRONTIER",
              "candidate_id": None,
              "public_target_original": f["public_target_original"],
              "public_target_transported": f["public_target_transported"],
              "raw_target_preimage_z": f["raw_target_reciprocals"],
              "known_masks": f["known_masks"],
              "pin_counts": PIN_COUNTS,
              "pin_policy": "first k source masks fixed to the archived exact witness; all pair, middle, and target-flag variables free",
              "construction_cap_seconds": 120,
              "solver_cap_seconds_per_case": CAP,
              "parent_cap_seconds_per_case": PARENT_CAP,
              "rss_cap_bytes": RSS_CAP,
              "workers": 1,
              "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                               "--random=20261011", "--maxtime=20"],
              "source_sha256": {key: sha(path) for key, path in files().items()}}
    save(path, record)
    print(record["status"])


def run():
    out_path = HERE / "result.json"
    if out_path.exists():
        raise FileExistsError(out_path)
    p = json.loads((HERE / "protocol.json").read_text())
    assert p["source_sha256"] == {key: sha(path) for key, path in files().items()}
    f = guarded.fixture()
    began = time.monotonic()
    circuit, metadata, build_seconds = guarded.old.build(f["raw_target_reciprocals"])
    assert build_seconds <= p["construction_cap_seconds"]
    assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss < RSS_CAP
    base_clauses = len(circuit.clauses)
    rows = []
    for count in p["pin_counts"]:
        pins = []
        for wires, mask in zip(metadata["masks"][:count], f["known_masks"][:count]):
            pins.extend((wire if mask >> bit & 1 else -wire)
                        for bit, wire in enumerate(wires))
        assert len(pins) == 9 * count
        circuit.clauses.extend(f"{literal} 0" for literal in pins)
        with tempfile.NamedTemporaryFile(prefix="n41_w9_pin_", suffix=".xcnf",
                                         dir="/private/tmp", delete=False) as stream:
            formula = Path(stream.name)
        try:
            write_start = time.monotonic()
            circuit.write(formula)
            write_seconds = time.monotonic() - write_start
            formula_hash = sha(formula)
            formula_bytes = formula.stat().st_size
            out_file = HERE / f"pin{count}.stdout.gz"
            err_file = HERE / f"pin{count}.stderr.gz"
            with tempfile.NamedTemporaryFile(dir="/private/tmp") as stdout_file, \
                 tempfile.NamedTemporaryFile(dir="/private/tmp") as stderr_file:
                solver_start = time.monotonic()
                proc = subprocess.Popen([str(SOLVER), *p["solver_flags"], str(formula)],
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
                    time.sleep(0.1)
                returncode = proc.wait()
                stdout_file.flush()
                stderr_file.flush()
                stdout = Path(stdout_file.name).read_bytes()
                stderr = Path(stderr_file.name).read_bytes()
            solver_seconds = time.monotonic() - solver_start
            with gzip.open(out_file, "wb", compresslevel=6) as stream:
                stream.write(stdout)
            with gzip.open(err_file, "wb", compresslevel=6) as stream:
                stream.write(stderr)
            status = ("RESOURCE_GATE_EXCEEDED" if memory_exceeded else
                      "SAT_PENDING_GROUP_REPLAY" if b"s SATISFIABLE" in stdout else
                      "UNSAT" if b"s UNSATISFIABLE" in stdout else
                      "BOUNDED_UNKNOWN")
            rows.append({"pin_count": count, "pinned_bits": len(pins),
                         "status": status, "solver_started": True,
                         "solver_timed_out": timed_out,
                         "solver_rss_exceeded": memory_exceeded,
                         "solver_returncode": returncode,
                         "solver_seconds": solver_seconds,
                         "write_seconds": write_seconds,
                         "peak_combined_rss_bytes": peak,
                         "formula_clauses": len(circuit.clauses),
                         "formula_bytes": formula_bytes,
                         "formula_sha256": formula_hash,
                         "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                         "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                         "active_restart_lines": sum(line.startswith(b"c rst")
                                                     for line in stdout.splitlines())})
            print(json.dumps({"pin_count": count, "status": status,
                              "solver_seconds": solver_seconds,
                              "active_restart_lines": rows[-1]["active_restart_lines"]}),
                  flush=True)
        finally:
            formula.unlink(missing_ok=True)
            del circuit.clauses[base_clauses:]
    report = {"status": "COMPLETE_GUARDED_MASK_PIN_FRONTIER",
              "candidate_id": None,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": sha(Path(__file__)),
              "construction_seconds": build_seconds,
              "total_wall_seconds": time.monotonic() - began,
              "peak_self_ru_maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "base_formula": guarded.old.profile(circuit, metadata, build_seconds),
              "rows": rows}
    save(out_path, report)
    print(report["status"])


if __name__ == "__main__":
    if sys.argv[1:] == ["freeze"]:
        freeze()
    elif sys.argv[1:] == ["run"]:
        run()
    else:
        raise SystemExit("usage: run.py freeze|run")
