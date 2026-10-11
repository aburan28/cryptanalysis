"""Repeat the unpinned positive query with the XOR matrix enabled."""

import hashlib
import json
import psutil
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main():
    base = json.loads((HERE / "protocol.json").read_text())
    assert base["status"] == "FROZEN_DERIVATIVE_TWO_PAIR_N41"
    formula = HERE / "positive.xcnf"
    assert sha(formula) == base["formulas"]["positive"]["sha256"]
    flags = [*base["solver_flags"], "--maxmatrixrows=2000",
             "--maxmatrixcols=3500", "--maxnummatrices=10"]
    frozen = {"status": "FROZEN_DERIVATIVE_WIDE_MATRIX_POSITIVE",
              "base_protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": sha(__file__), "formula_sha256": sha(formula),
              "solver_sha256": sha(base["solver"]), "flags": flags,
              "workers": 1, "parent_cap_seconds": 35,
              "rss_cap_bytes": 4 * 1024**3}
    protocol = HERE / "matrix_protocol.json"
    if protocol.exists():
        assert json.loads(protocol.read_text()) == frozen
    else:
        save(protocol, frozen)
    start = time.monotonic_ns()
    with (HERE / "matrix_positive.stdout").open("wb") as out, \
         (HERE / "matrix_positive.stderr").open("wb") as err:
        child = subprocess.Popen([base["solver"], *flags, str(formula)],
                                 stdout=out, stderr=err)
        proc = psutil.Process(child.pid)
        parent = psutil.Process()
        peak = 0
        killed_by = None
        while child.poll() is None:
            try:
                rss = proc.memory_info().rss + parent.memory_info().rss
            except psutil.NoSuchProcess:
                rss = parent.memory_info().rss
            peak = max(peak, rss)
            if rss > frozen["rss_cap_bytes"]:
                killed_by = "RSS_CAP"
                child.kill()
                break
            if (time.monotonic_ns()-start)/1e9 > 35:
                killed_by = "PARENT_TIME_CAP"
                child.kill()
                break
            time.sleep(0.1)
        code = child.wait()
    stdout = (HERE / "matrix_positive.stdout").read_bytes()
    status = ("RESOURCE_GATE_EXCEEDED" if killed_by == "RSS_CAP" else
              "BOUNDED_UNKNOWN" if killed_by else
              "UNSAT" if b's UNSATISFIABLE' in stdout else
              "SAT_RELAXED_MODEL" if b's SATISFIABLE' in stdout else
              "BOUNDED_UNKNOWN")
    result = {"status": status, "return_code": code, "killed_by": killed_by,
              "wall_ns": time.monotonic_ns()-start,
              "peak_combined_rss_bytes": peak,
              "stdout_sha256": sha(HERE / "matrix_positive.stdout"),
              "stderr_sha256": sha(HERE / "matrix_positive.stderr"),
              "matrix_protocol_sha256": sha(protocol)}
    save(HERE / "matrix_positive.json", result)
    print(status, "wall_s", round(result["wall_ns"]/1e9, 3), "rss", peak)


if __name__ == "__main__":
    main()
