#!/usr/bin/env python3
"""Check that every capped N83 solver cell entered conflict search."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    rows = []
    for weight in (5, 6, 7, 8):
        path = HERE / f"w{weight}.json"
        run = json.loads(path.read_text())
        assert run["status"] == "BOUNDED_UNKNOWN"
        output = gzip.decompress((HERE / f"w{weight}.stdout.gz").read_bytes()
                                 ).decode(errors="replace")
        restarts = [line for line in output.splitlines()
                    if line.startswith("c rst  ")]
        assert restarts, weight
        assert "c [branch]" in output or len(restarts) > 1
        rows.append({"weight": weight, "run_sha256": sha(path),
                     "solver_stdout_sha256": sha(HERE / f"w{weight}.stdout.gz"),
                     "search_began": True, "restart_log_lines": len(restarts),
                     "last_restart_log_line": restarts[-1],
                     "timed_out": run["timed_out"],
                     "final_conflicts_reported": run["last_reported_conflicts"]})
    assert [row["timed_out"] for row in rows] == [True, True, True, False]
    assert rows[3]["final_conflicts_reported"] == 100002
    result = {"status": "PASS", "auditor_source_sha256": sha(__file__),
              "rows": rows}
    path = HERE / "trace_audit.json"
    assert not path.exists()
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps([{"weight": row["weight"],
                       "search_began": row["search_began"],
                       "restart_lines": row["restart_log_lines"]}
                      for row in rows]))


if __name__ == "__main__":
    main()
