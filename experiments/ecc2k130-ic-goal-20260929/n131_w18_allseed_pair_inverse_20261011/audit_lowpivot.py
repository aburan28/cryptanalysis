"""Run a complete second all-seed scan with independent low-pivot reduction."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, payload):
    with path.open("x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    paths = {"auditor": HERE / "audit_lowpivot.py",
             "generator": HERE / "generate_lowpivot.py",
             "lowpivot_source": HERE / "native_lowpivot.cpp",
             "lowpivot_binary": HERE / "native_lowpivot",
             "original_source": HERE / "native.cpp",
             "support": SUPPORT,
             "run_protocol": HERE / "protocol.json"}
    for index in range(3):
        paths[f"original_query_{index}"] = HERE / f"query_{index:03d}.json"
    return paths


def freeze():
    assert not (HERE / "lowpivot_protocol.json").exists()
    protocol = {"status": "FROZEN_BEFORE_LOW_PIVOT_SCAN",
                "curve_id": "EC1N131Ckb1heb5f1998f20b",
                "cases": json.loads((HERE / "protocol.json").read_text())["cases"][:3],
                "workers": 1, "per_case_parent_cap_seconds": 180,
                "native_query_cap_seconds": 120,
                "rss_cap_bytes": 4 * 1024**3,
                "comparison": "same 262143 W18 seeds and both product branches; reverse GF(2) elimination pivot direction and compare all semantic counters and hits",
                "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save_new(HERE / "lowpivot_protocol.json", protocol)
    print("low-pivot scan frozen", len(protocol["cases"]), "cases")


def run():
    protocol_path = HERE / "lowpivot_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_LOW_PIVOT_SCAN"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    rows = []
    for index, case in enumerate(protocol["cases"]):
        output = HERE / f"lowpivot_query_{index:03d}.json"
        stdout = HERE / f"lowpivot_stdout_{index:03d}.txt"
        stderr = HERE / f"lowpivot_stderr_{index:03d}.txt"
        assert not any(path.exists() for path in (output, stdout, stderr))
        cmd = [str(HERE / "native_lowpivot"), str(SUPPORT), str(case["coordinate"]),
               str(case["rotation"]), str(output), str(protocol["native_query_cap_seconds"])]
        started = time.perf_counter_ns()
        with stdout.open("x") as out, stderr.open("x") as err:
            try:
                proc = subprocess.run(cmd, cwd=HERE, stdout=out, stderr=err,
                                      timeout=protocol["per_case_parent_cap_seconds"])
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                returncode = None
        parent_ns = time.perf_counter_ns() - started
        raw = json.loads(output.read_text()) if output.exists() else None
        original = json.loads((HERE / f"query_{index:03d}.json").read_text())
        if returncode == 0 and raw is not None:
            for key in ("setup_ns_exploratory", "query_ns_exploratory", "peak_rss_bytes"):
                raw.pop(key)
                original.pop(key)
            assert raw == original
            status = "PASS_FULL_SEED_SEMANTIC_REPLAY"
        else:
            status = "CENSORED_PARENT_TIME" if returncode is None else "PRODUCER_FAILURE"
        row = {"name": case["name"], "status": status,
               "returncode": returncode, "parent_wall_ns_exploratory": parent_ns,
               "output_sha256": sha(output) if output.exists() else None,
               "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)}
        rows.append(row)
        save_new(HERE / f"lowpivot_receipt_{index:03d}.json", row)
        print(case["name"], status, flush=True)
        if status != "PASS_FULL_SEED_SEMANTIC_REPLAY":
            break
    result = {"status": "PASS" if len(rows) == len(protocol["cases"]) and
              all(row["status"] == "PASS_FULL_SEED_SEMANTIC_REPLAY" for row in rows)
              else "INCOMPLETE", "protocol_sha256": sha(protocol_path), "rows": rows}
    save_new(HERE / "lowpivot_audit.json", result)
    print(result["status"])


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else run()
