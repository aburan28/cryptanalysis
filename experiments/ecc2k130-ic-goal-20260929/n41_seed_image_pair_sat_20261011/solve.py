"""Bounded unpinned CryptoMiniSat runs for frozen derivative formulas."""

import hashlib
import json
import psutil
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol.json"
SOLVER_PROTOCOL = HERE / "solver_protocol.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    p = json.loads(PROTOCOL.read_text())
    assert p["status"] == "FROZEN_N41_SEED_IMAGE_PAIR_SAT"
    assert p["sha256"]["circuit"] == sha(HERE / "circuit.py")
    assert p["sha256"]["prepare"] == sha(HERE / "prepare.py")
    assert p["sha256"]["solver"] == sha(p["solver"])
    for label, shape in p["cases"].items():
        assert shape["sha256"] == sha(HERE / f"{label}.xcnf")
    identity = {"status": "FROZEN_BEFORE_UNPINNED_SOLVES",
                "protocol_sha256": sha(PROTOCOL), "runner_sha256": sha(__file__),
                "solver_sha256": sha(p["solver"]),
                "cases": ["positive", "control_23", "control_229"]}
    if SOLVER_PROTOCOL.exists():
        assert json.loads(SOLVER_PROTOCOL.read_text()) == identity
    else:
        save(SOLVER_PROTOCOL, identity)
    for label in identity["cases"]:
        if (HERE / f"{label}.json").exists():
            continue
        start = time.monotonic_ns()
        with (HERE / f"{label}.stdout").open("wb") as out, \
             (HERE / f"{label}.stderr").open("wb") as err:
            child = subprocess.Popen([p["solver"], *p["solver_flags"],
                                      str(HERE / f"{label}.xcnf")],
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
                if rss > p["rss_cap_bytes"]:
                    killed_by = "RSS_CAP"
                    child.kill()
                    break
                if (time.monotonic_ns()-start)/1e9 > p["parent_cap_seconds"]:
                    killed_by = "PARENT_TIME_CAP"
                    child.kill()
                    break
                time.sleep(0.1)
            code = child.wait()
        wall_ns = time.monotonic_ns()-start
        stdout = (HERE / f"{label}.stdout").read_bytes()
        stderr = (HERE / f"{label}.stderr").read_bytes()
        if killed_by:
            status = "BOUNDED_UNKNOWN" if killed_by == "PARENT_TIME_CAP" else "RESOURCE_GATE_EXCEEDED"
        elif b's UNSATISFIABLE' in stdout:
            status = "UNSAT"
        elif b's SATISFIABLE' in stdout:
            status = "SAT_RELAXED_MODEL"
        else:
            status = "BOUNDED_UNKNOWN"
        result = {"status": status, "label": label,
                  "return_code": code, "killed_by": killed_by,
                  "wall_ns": wall_ns, "peak_combined_rss_bytes": peak,
                  "stdout_sha256": sha(HERE / f"{label}.stdout"),
                  "stderr_sha256": sha(HERE / f"{label}.stderr"),
                  "solver_protocol_sha256": sha(SOLVER_PROTOCOL),
                  "search_started": b'c [branch]' in stdout or b'c [scc]' in stdout or
                                    b'c [xor]' in stdout or b'c [conflicts]' in stdout}
        save(HERE / f"{label}.json", result)
        print(label, status, "wall_s", round(wall_ns/1e9, 3),
              "rss", peak, "return", code, flush=True)


if __name__ == "__main__":
    main()
