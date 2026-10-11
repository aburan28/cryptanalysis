"""Solve one source-bound pinned pair-output XCNF as a wiring control."""

import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
CMS = Path("/opt/homebrew/bin/cryptominisat5")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cap_child():
    resource.setrlimit(resource.RLIMIT_AS, (4294967296, 4294967296))


def main():
    protocol = json.loads((HERE / "pair_solver_protocol.json").read_text())
    paths = {"script": Path(__file__), "formula": HERE / "pair_pinned.xcnf",
             "preflight": HERE / "pair_preflight_result.json", "solver": CMS.resolve()}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    cmd = [str(CMS), "--threads=1", "--maxtime=60", "--zero-exit-status",
           "--verb=1", "--printsol=1", str(paths["formula"])]
    start = time.monotonic_ns()
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=70, preexec_fn=cap_child)
        exit_code = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
        status = "SAT_MODEL_UNAUDITED" if "s SATISFIABLE" in stdout else (
            "UNSAT" if "s UNSATISFIABLE" in stdout else "BOUNDED_UNKNOWN")
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        status = "PARENT_TIMEOUT"
    wall_ns = time.monotonic_ns() - start
    (HERE / "pair_solver.stdout.txt").write_text(stdout)
    (HERE / "pair_solver.stderr.txt").write_text(stderr)
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    result = {"status": status, "exit_code": exit_code,
              "command": cmd, "wall_ns": wall_ns, "peak_child_rss_bytes": peak,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "stdout_sha256": digest(HERE / "pair_solver.stdout.txt"),
              "stderr_sha256": digest(HERE / "pair_solver.stderr.txt"),
              "protocol_sha256": digest(HERE / "pair_solver_protocol.json")}
    with (HERE / "pair_solver_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status, "exit_code": exit_code,
                      "wall_ns": wall_ns, "peak_child_rss_bytes": peak}))


if __name__ == "__main__":
    main()
