"""Offline audit of the bounded W16 decision-graph search."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    control = json.loads((HERE / "control.json").read_text())
    query = json.loads((HERE / "query.json").read_text())
    truth = json.loads((HERE / "audit.json").read_text())
    assert truth["status"] == "PASS_EXHAUSTIVE_65536_MASKS_AND_RECEIPT_AUDIT"
    assert query["source_sha256"] == protocol["source_sha256"]
    assert query["target_q"] == control["target_q"] == protocol["target_q"]
    assert query["formula"] == control["formula"]
    assert query["output_sha256"] == {
        "stdout": sha(HERE / "solver.stdout.txt"),
        "stderr": sha(HERE / "solver.stderr.txt")}
    assert query["status"] == "CENSORED_TIME"
    assert query["stop_reason"] == "SAFE_WALL_STOP"
    assert query["solver_status_lines"] == [] and query["model_lines"] == 0
    assert query["phase_seconds"]["total"] <= protocol["total_cap_seconds"]
    assert query["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    stdout = (HERE / "solver.stdout.txt").read_text(errors="replace")
    restarts = sum(line.startswith("c rst ") for line in stdout.splitlines())
    assert restarts > 0
    assert "s SATISFIABLE" not in stdout and "s UNSATISFIABLE" not in stdout
    result = {"status": "PASS_CENSORED_SEARCH_RECEIPT",
              "solver_restart_lines": restarts,
              "solver_cpu_seconds_sampled": query["sampled_solver_cpu_seconds"],
              "search_wall_seconds": query["phase_seconds"]["search"],
              "total_wall_seconds": query["phase_seconds"]["total"],
              "peak_combined_rss_bytes": query["sampled_peak_combined_rss_bytes"],
              "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                "control": sha(HERE / "control.json"),
                                "query": sha(HERE / "query.json"),
                                "stdout": sha(HERE / "solver.stdout.txt"),
                                "stderr": sha(HERE / "solver.stderr.txt")}}
    with (HERE / "query_audit.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "restart_lines": restarts}))


if __name__ == "__main__":
    main()
