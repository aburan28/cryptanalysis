"""Run frozen cutoff-one XCNF controls from checked compressed artifacts."""

import argparse
import gzip
import hashlib
import json
import resource
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
CMS = Path("/opt/homebrew/bin/cryptominisat5").resolve()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("constructed", "unpinned_constructed"), required=True)
    args = parser.parse_args()
    protocol_path = HERE / "solver_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": HERE / "run_solver.py", "solver": CMS}
    for mode in ("constructed", "unpinned_constructed"):
        paths["%s_formula" % mode] = HERE / ("four_%s.xcnf.gz" % mode)
        paths["%s_build" % mode] = HERE / ("four_%s_build.json" % mode)
    assert protocol["source_sha256"] == {name: digest(path) for name, path in paths.items()}
    limit = protocol["modes"][args.mode]
    assert protocol["rss_cap_bytes"] == 4294967296
    packed = paths["%s_formula" % args.mode]
    build = json.loads(paths["%s_build" % args.mode].read_text())
    out_path = HERE / ("%s_solver.stdout.txt" % args.mode)
    err_path = HERE / ("%s_solver.stderr.txt" % args.mode)
    with tempfile.TemporaryDirectory(prefix="n131_w18_cutoff1_", dir="/private/tmp") as temporary:
        formula = Path(temporary) / "input.xcnf"
        with gzip.open(packed, "rb") as source, formula.open("wb") as target:
            shutil.copyfileobj(source, target, 1024*1024)
        assert digest(formula) == build["xcnf"]["sha256"]
        cmd = [str(CMS), "--threads=1", "--maxtime=%d" % limit["solver_wall_cap_seconds"],
               "--zero-exit-status", "--verb=1", "--printsol=1", str(formula)]
        start = time.monotonic_ns()
        peak_sampled, stop_reason = 0, None
        with out_path.open("x") as out, err_path.open("x") as err:
            process = subprocess.Popen(cmd, stdout=out, stderr=err)
            observed = psutil.Process(process.pid)
            while process.poll() is None:
                try:
                    peak_sampled = max(peak_sampled, observed.memory_info().rss)
                except psutil.NoSuchProcess:
                    break
                if peak_sampled > protocol["rss_cap_bytes"]:
                    stop_reason = "RSS_CAP"
                    process.kill()
                    break
                if time.monotonic_ns()-start > limit["parent_wall_cap_seconds"]*1_000_000_000:
                    stop_reason = "PARENT_TIMEOUT"
                    process.kill()
                    break
                time.sleep(0.05)
            exit_code = process.wait()
        wall_ns = time.monotonic_ns()-start
    stdout = out_path.read_text()
    status = stop_reason or ("SAT_MODEL_UNAUDITED" if "s SATISFIABLE" in stdout else
                             "UNSAT" if "s UNSATISFIABLE" in stdout else
                             "BOUNDED_UNKNOWN")
    result = {"status": status, "mode": args.mode, "candidate_id": None,
              "command": cmd, "exit_code": exit_code, "wall_ns": wall_ns,
              "peak_child_rss_bytes": max(peak_sampled,
                                          resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),
              "peak_sampled_rss_bytes": peak_sampled,
              "source_sha256": protocol["source_sha256"],
              "formula_sha256_uncompressed": build["xcnf"]["sha256"],
              "stdout_sha256": digest(out_path), "stderr_sha256": digest(err_path),
              "protocol_sha256": digest(protocol_path)}
    with (HERE / ("%s_solver_result.json" % args.mode)).open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"mode": args.mode, "status": status,
                      "wall_ns": wall_ns, "peak_child_rss_bytes": result["peak_child_rss_bytes"]}))


if __name__ == "__main__":
    main()
