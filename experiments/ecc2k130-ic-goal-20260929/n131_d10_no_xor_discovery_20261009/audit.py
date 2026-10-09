#!/usr/bin/env python3
"""Independently audit the terminal preflight and matrix-selection geometry."""

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "n131_d10_bridge_projection_20261009/ordinary_precompute_R1"
PREFLIGHT = HERE / "preflight"
PROTOCOL = HERE / "protocol.json"

GOOD_MATRIX = re.compile(r"\[matrix\] Good\s+matrix\s+\d+\s+(\d+) x\s*(\d+)")
UNUSED_MATRIX = re.compile(r"\[matrix\] UNused\s+matrix\s+(\d+) x\s*(\d+)")
TOO_MANY = re.compile(r"Too many rows in matrix: (\d+)")
FOUND = re.compile(r"\[occ-xor\] found\s+(\d+)")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def profile(path):
    lines = path.read_text(errors="replace").splitlines()
    matrix_init = sum("[find&init matx] performing matrix init" in line for line in lines)
    first_found = [int(m.group(1)) for line in lines if (m := FOUND.search(line))]
    dimensions = [(int(m.group(1)), int(m.group(2)))
                  for line in lines
                  if (m := GOOD_MATRIX.search(line) or UNUSED_MATRIX.search(line))]
    oversized = [int(m.group(1)) for line in lines if (m := TOO_MANY.search(line))]
    return {
        "sha256": sha(path), "bytes": path.stat().st_size,
        "matrix_init_count": matrix_init,
        "occurrence_xor_discovery_counts": first_found,
        "max_reported_matrix_rows": max((x[0] for x in dimensions), default=None),
        "max_reported_matrix_columns": max((x[1] for x in dimensions), default=None),
        "oversized_matrix_rows": sorted(set(oversized)),
        "auto_disable_matrix_count": sum("TODO disable matrix, performing badly" in line for line in lines),
        "sls_disabled_by_matrix_count": sum("disabling SLS since matrix is found" in line for line in lines),
        "selected_ten_matrix_count": sum("Using 10 matrices" in line for line in lines),
        "solver_status_lines": [line for line in lines if line.startswith("s ")],
        "solver_model_line_count": sum(line.startswith("v ") for line in lines),
    }


def main():
    path = PREFLIGHT / "independent_audit.json"
    if path.exists():
        raise FileExistsError(path)
    protocol = json.loads(PROTOCOL.read_text())
    started = json.loads((PREFLIGHT / "started.json").read_text())
    result = json.loads((PREFLIGHT / "result.json").read_text())
    process = json.loads((PREFLIGHT / "solver_process.json").read_text())
    assert started["protocol_sha256"] == sha(PROTOCOL)
    assert result["source_sha256"]["protocol"] == sha(PROTOCOL)
    assert result["source_sha256"]["formula"] == protocol["source_sha256"]["formula"]
    assert result["source_sha256"]["solver"] == protocol["source_sha256"]["solver"]
    assert result["source_sha256"]["runtime"] == protocol["source_sha256"]["runtime"]
    assert started["solver_command"] == process["command"]
    assert "--xor=0" in process["command"]
    assert "--maxtime=88" in process["command"]
    assert process["command"][-1].endswith("budget1/projected.xcnf")
    assert result["status"] in ("CENSORED_TIME", "SAT_MODEL_REQUIRES_INDEPENDENT_AUDIT", "OOM", "INDETERMINATE", "UNSAT")
    assert result["solver_wall_seconds"] <= 100
    import psutil
    try:
        live = psutil.Process(process["pid"])
    except psutil.NoSuchProcess:
        pass
    else:
        assert live.create_time() != process["create_time_epoch"], "solver process still live"
    old = profile(BASELINE / "cryptominisat.stdout.txt")
    new = profile(PREFLIGHT / "cryptominisat.stdout.txt")
    assert old["sha256"] == protocol["source_sha256"]["old_solver_log"]
    assert new["sha256"] == result["source_sha256"]["stdout"]
    assert sha(PREFLIGHT / "cryptominisat.stderr.txt") == result["source_sha256"]["stderr"]
    assert old["occurrence_xor_discovery_counts"] and old["occurrence_xor_discovery_counts"][0] > 0
    assert old["oversized_matrix_rows"] and max(old["oversized_matrix_rows"]) > 10000
    if (new["matrix_init_count"] >= 2 and
            not new["occurrence_xor_discovery_counts"] and
            not new["oversized_matrix_rows"] and
            new["max_reported_matrix_rows"] is not None and
            new["max_reported_matrix_rows"] <= 10000 and
            result["status"] == "CENSORED_TIME"):
        status = "PASS_NO_XOR_REDISCOVERY"
    else:
        status = "INCONCLUSIVE_OR_FAILED_BRIDGE_PRESERVATION"
    receipt = {
        "kind": "n131_d10_no_xor_rediscovery_independent_solver_log_audit",
        "status": status,
        "same_source_formula": result["source_sha256"]["formula"] == protocol["source_sha256"]["formula"],
        "baseline": old, "preflight": new,
        "preflight_result_status": result["status"],
        "preflight_combined_peak_rss_bytes": result["combined_peak_rss_bytes"],
        "preflight_solver_wall_seconds": result["solver_wall_seconds"],
        "preflight_solver_cpu_seconds_lower_bound": result["solver_cpu_seconds_lower_bound"],
        "source_sha256": {"protocol": sha(PROTOCOL), "started": sha(PREFLIGHT / "started.json"),
                          "result": sha(PREFLIGHT / "result.json"),
                          "audit_script": sha(Path(__file__))},
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "baseline": old, "preflight": new}))


if __name__ == "__main__":
    main()
