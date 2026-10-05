#!/usr/bin/env python3
"""Replay the folded two-digit policy against the frozen double-pair inputs."""

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line):
    return dict(item.split("=", 1) for item in line.strip().split() if "=" in item)


def run(bench, arm, case, scalar_path):
    command = [str(bench), arm, case["curve"]["name"], str(case["point_index"]),
               str(scalar_path)]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=120,
                              check=False)
        row = {"arm": arm, "command": command, "returncode": done.returncode,
               "stdout": done.stdout, "stderr": done.stderr}
        if done.returncode == 0:
            row["fields"] = fields(done.stdout)
    except subprocess.TimeoutExpired as exc:
        row = {"arm": arm, "command": command, "returncode": None, "timeout": True,
               "stdout": (exc.stdout or b"").decode(errors="replace"),
               "stderr": (exc.stderr or b"").decode(errors="replace")}
    return row


def score(row):
    f = row["fields"]
    return 10 * int(f["triples"]) + 16 * int(f["adds"]) + int(f["rotations"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name(
                        "tail-double-fold-regression.json"))
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    root = directory.parents[1]
    fixture_path = directory / "tail-double-inputs.json"
    prior_path = directory / "tail-double-panel.json"
    fixture = json.loads(fixture_path.read_text())
    prior = {case["id"]: case for case in json.loads(prior_path.read_text())["results"]}
    bench = args.bench.resolve()
    source = [Path(__file__).resolve(), directory / "make_tau_tail_double_fold.py",
              root / "src" / "generated" / "tau_tail_double_fold.h",
              directory / "make_tau_tail_double_residue.py",
              root / "src" / "generated" / "tau_tail_double_residue.h",
              root / "src" / "ec_tau.c", root / "src" / "ec_tau_internal.h",
              directory / "bench.c"]
    receipt = {"schema": 1, "status": "running", "cpu_timing_claim": False,
               "environment": {"os": platform.platform(), "architecture": platform.machine()},
               "binary_sha256": sha(bench), "fixture_sha256": sha(fixture_path),
               "prior_panel_sha256": sha(prior_path),
               "source_sha256": {str(path.relative_to(root)): sha(path) for path in source},
               "cases": []}
    failure = None
    for case in fixture["cases"]:
        scalar_path = directory / case["scalar_file"]
        rows = [run(bench, arm, case, scalar_path)
                for arm in ("tail-double", "tail-double-fold", "tail-double-residue")]
        record = {"id": case["id"], "scalar_sha256": sha(scalar_path),
                  "runs": {row["arm"]: row for row in rows}}
        receipt["cases"].append(record)
        try:
            assert record["scalar_sha256"] == case["scalar_file_sha256"]
            for row in rows:
                assert row["returncode"] == 0
                f = row["fields"]
                assert f["verified"] == "1" and int(f["tail_double_checks"]) == 4096
                assert f["output_digest"] == case["expected_output_digest"]
                assert f["input_digest"] == case["input_digest"]
                assert int(f["count"]) == case["scalars"]
            assert score(rows[0]) == score(rows[1]) == score(rows[2])
            for metric in ("triples", "adds", "rotations"):
                assert len({row["fields"][metric] for row in rows}) == 1
            assert score(rows[0]) == sum(
                int(prior[case["id"]]["runs"]["tail-double"]["operations"][key]) * weight
                for key, weight in (("triples", 10), ("adds", 16), ("rotations", 1)))
            assert int(rows[0]["fields"]["static_map_bytes"]) == 106087
            assert int(rows[1]["fields"]["static_map_bytes"]) == 37918
            assert int(rows[2]["fields"]["static_map_bytes"]) == 31660
            record["weighted_score"] = score(rows[1])
            record["status"] = "pass"
        except (AssertionError, KeyError, ValueError) as exc:
            record["status"] = "fail"
            failure = f"{case['id']}: {exc or 'assertion failed'}"
            break
    receipt["status"] = "pass" if failure is None else "fail"
    if failure is not None:
        receipt["failure"] = failure
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "cases": len(receipt["cases"]),
                      "fold_bytes": 37918, "residue_bytes": 31660,
                      "original_bytes": 106087,
                      "failure": failure}, sort_keys=True))
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
