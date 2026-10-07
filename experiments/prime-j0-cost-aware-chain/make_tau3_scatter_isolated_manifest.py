#!/usr/bin/env python3
"""Bind the frozen scattered-tau scalar panel to the isolated benchmark service."""

import argparse
import hashlib
import json
from pathlib import Path


EXPERIMENT = Path("experiments/prime-j0-cost-aware-chain")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--cgroup", type=Path, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-nodes", required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(not path.is_absolute() for path in
           (args.binary, args.workdir, args.cgroup, args.output)):
        parser.error("all paths must be absolute paths on the benchmark host")
    if not args.binary.is_file() or not args.workdir.is_dir():
        parser.error("binary and workdir must exist on the benchmark host")
    if not 1 <= args.repetitions <= 1000 or not 0 < args.timeout_s <= 86400:
        parser.error("repetitions or timeout outside isolated runner limits")

    root = args.workdir
    folder = root / EXPERIMENT
    design = folder / "tau3-scatter-design.json"
    inputs_path = folder / "tau3-scatter-inputs/inputs.json"
    model = folder / "tau3-scatter-panel.json"
    native_panel = folder / "tau3-scatter-native-panel.json"
    inputs = json.loads(inputs_path.read_text())
    if inputs.get("status") != "fresh_disjoint_fixture" or inputs.get("schema") != 1:
        parser.error("expected the frozen fresh scalar fixture")
    if sha256(design) != inputs.get("design_sha256"):
        parser.error("design hash differs from the frozen input manifest")
    expected = json.loads(model.read_text())
    if len(inputs["cases"]) != 8 or len(expected["rows"]) != 8:
        parser.error("expected the eight frozen scalar cases")
    if not all(row.get("verified") for row in expected["rows"]):
        parser.error("the frozen model has an unverified case")
    native = json.loads(native_panel.read_text())
    if native.get("status") != "pass" or len(native.get("rows", [])) != 16:
        parser.error("expected the verified 16-arm native panel")
    native_rows = {(row["case_id"], row["mode"]): row for row in native["rows"]}
    pair_fields = ["curve", "point_index", "count", "base_x", "base_y",
                   "endo_lambda", "input_digest", "output_digest"]

    cases = []
    artifacts = [root / "CMakeLists.txt", root / "src/ec_tau.c",
                 root / "src/ec_tau_internal.h", root / "src/generated/tau3_fused.h",
                 root / "src/generated/tau3_scatter.h", folder / "bench.c",
                 folder / "make_tau3_scatter_isolated_manifest.py",
                 folder / "check_tau3_scatter_native_panel.py", design,
                 inputs_path, model, native_panel, args.binary,
                 args.binary.parent / "CMakeCache.txt"]
    for case in inputs["cases"]:
        scalar_file = folder / "tau3-scatter-inputs" / case["scalar_file"]
        if sha256(scalar_file) != case["scalar_file_sha256"]:
            parser.error("scalar-file hash differs for " + case["id"])
        artifacts.append(scalar_file)
        point_index = case["id"].rsplit("point", 1)[1]
        common = [case["curve"]["name"], point_index, str(scalar_file)]
        control = native_rows[(case["id"], "tau3-fused-pos")]
        scatter = native_rows[(case["id"], "tau3-scatter-pos")]
        if not control.get("gate_pass") or not scatter.get("gate_pass"):
            parser.error("native panel rejected " + case["id"])
        fields = control["fields"]
        if any(fields.get(field) != scatter["fields"].get(field) for field in pair_fields):
            parser.error("native paired fields differ for " + case["id"])
        if (fields["curve"] != case["curve"]["name"] or
            fields["point_index"] != point_index or
            fields["count"] != str(case["count"]) or
            fields["base_x"] != case["base_x"] or
            fields["base_y"] != case["base_y"]):
            parser.error("native panel differs from frozen fixture for " + case["id"])
        cases.append({"id": case["id"],
                      "reference": [str(args.binary), "tau3-fused-pos"] + common,
                      "candidate": [str(args.binary), "tau3-scatter-pos"] + common,
                      "expected_fields": {field: fields[field] for field in pair_fields},
                      "expected_result": fields["output_digest"]})

    if any(not path.is_file() for path in artifacts):
        parser.error("a source, build, or fixture artifact is missing")
    manifest = {
        "schema": 1, "name": "tau3-scatter-native-isolated-replay",
        "workdir": str(root),
        "isolation": {"cgroup": str(args.cgroup), "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_nodes},
        "build": {"binary_sha256": sha256(args.binary),
                  "same_binary_for_both_modes": True,
                  "reference_mode": "tau3-fused-pos",
                  "candidate_mode": "tau3-scatter-pos"},
        "fixture": {"design_sha256": sha256(design),
                    "inputs_sha256": sha256(inputs_path),
                    "model_sha256": sha256(model),
                    "native_panel_sha256": sha256(native_panel),
                    "case_count": len(cases), "scalars_per_case": 4096},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s, "repetitions": args.repetitions,
        "measurement_boundary": "bench.c online_ms: sequential scalar multiplications over one frozen 4096-scalar case, after input loading and point-table preparation, before independent scalar replay; result is batch latency, not one-target DLP latency",
        "pair_fields": pair_fields, "result_field": "output_digest",
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "pairs": len(cases) * args.repetitions,
                      "manifest_sha256": sha256(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
