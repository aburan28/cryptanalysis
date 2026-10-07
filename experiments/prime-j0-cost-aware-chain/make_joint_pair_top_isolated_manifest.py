#!/usr/bin/env python3
"""Bind the bounded-top comparison to the serial isolated service."""

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
    parser.add_argument("--reference-mode", choices=("joint-pair-hex-pos",
                                                       "joint-window4-xplane-pos"),
                        default="joint-pair-hex-pos")
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
    design = folder / "joint-pair-top-design.json"
    inputs_path = folder / "joint-pair-top-inputs/inputs.json"
    native_panel = folder / "joint-pair-top-native-panel.json"
    inputs = json.loads(inputs_path.read_text())
    if inputs.get("status") != "fresh_disjoint_fixture" or inputs.get("schema") != 1 or \
            sha256(design) != inputs.get("design_sha256") or \
            inputs.get("source_sha256") != sha256(folder / "make_joint_pair_top_inputs.py") or \
            len(inputs.get("prior_manifest_sha256", {})) != 13:
        parser.error("expected the frozen fresh bounded-top fixture and design")
    native = json.loads(native_panel.read_text())
    if native.get("status") != "pass" or len(native.get("rows", [])) != 32 or \
            len(native.get("models", [])) != 8:
        parser.error("expected the verified 32-arm native panel and eight independent models")
    if native.get("binary_sha256") != sha256(args.binary) or \
            native.get("cmake_cache_sha256") != sha256(args.binary.parent / "CMakeCache.txt"):
        parser.error("native panel was generated with a different binary or build")
    provenance = {"design_sha256": design, "inputs_sha256": inputs_path,
                  "source_sha256": folder / "check_joint_pair_top_panel.py",
                  "independent_model_source_sha256": folder / "check_joint_pair_panel.py",
                  "top_map_producer_sha256": folder / "make_joint_pair_top_map.py",
                  "top_map_header_sha256": root / "src/generated/joint_pair_top_map.h",
                  "pair_map_header_sha256": root / "src/generated/joint_pair_map.h",
                  "bench_source_sha256": folder / "bench.c",
                  "ec_tau_source_sha256": root / "src/ec_tau.c",
                  "ec_tau_header_sha256": root / "src/ec_tau_internal.h"}
    if any(native.get(field) != sha256(path) for field, path in provenance.items()):
        parser.error("native panel source or fixture hashes differ")
    native_rows = {(row["case_id"], row["mode"]): row for row in native["rows"]}
    if len(native_rows) != 32:
        parser.error("native panel has duplicate case/mode rows")
    pair_fields = ["curve", "point_index", "count", "base_x", "base_y",
                   "endo_lambda", "input_digest", "output_digest"]
    artifacts = [root / "CMakeLists.txt", root / "src/ec_tau.c", root / "src/ec_tau_internal.h",
                 root / "src/generated/joint_pair_map.h",
                 root / "src/generated/joint_pair_top_map.h",
                 root / "src/generated/joint_window4.h",
                 root / "src/generated/joint_window4_hot.h",
                 root / "src/ca_internal.h", root / "src/group_ec.c", root / "src/modarith.c",
                 root / "tests/test_curve.c", folder / "bench.c", design, inputs_path,
                 native_panel, folder / "joint-window4-design.json",
                 folder / "joint-window4-inputs/inputs.json",
                 folder / "joint-window4-hot-design.json",
                 folder / "joint-window4-hot-inputs/inputs.json",
                 folder / "joint-window4-plane-design.json",
                 folder / "joint-window4-plane-inputs/inputs.json",
                 folder / "joint-window4-zero-design.json",
                 folder / "joint-window4-zero-inputs/inputs.json",
                 folder / "joint-window4-zero-native-panel.json",
                 folder / "joint-pair-design.json",
                 folder / "joint-pair-inputs/inputs.json",
                 folder / "joint-pair-native-panel.json",
                 folder / "compact-pos-panel.json",
                 folder / "make_joint_window4_hot_design.py",
                 folder / "make_joint_window4_hot_inputs.py",
                 folder / "make_joint_window4_hot_map.py",
                 folder / "make_joint_window4_plane_design.py",
                 folder / "make_joint_window4_plane_inputs.py",
                 folder / "make_joint_window4_zero_design.py",
                 folder / "make_joint_window4_zero_inputs.py",
                 folder / "make_joint_pair_design.py",
                 folder / "make_joint_pair_inputs.py",
                 folder / "make_joint_pair_map.py",
                 folder / "make_joint_pair_top_design.py",
                 folder / "make_joint_pair_top_inputs.py",
                 folder / "make_joint_pair_top_map.py",
                 folder / "make_joint_window4_map.py",
                 folder / "check_joint_window4_zero_panel.py",
                 folder / "check_joint_pair_panel.py",
                 folder / "check_joint_pair_top_panel.py",
                 folder / "make_joint_pair_top_isolated_manifest.py", args.binary,
                 args.binary.parent / "CMakeCache.txt"]
    frozen = json.loads(design.read_text())
    base_pair_design = folder / "joint-pair-design.json"
    base_pair_inputs = folder / "joint-pair-inputs/inputs.json"
    if frozen.get("base_pair_design_sha256") != sha256(base_pair_design) or \
            frozen.get("training_inputs_sha256") != sha256(base_pair_inputs) or \
            frozen.get("source_sha256") != sha256(folder / "make_joint_pair_top_design.py") or \
            frozen.get("top_map_producer_sha256") != sha256(
                folder / "make_joint_pair_top_map.py") or \
            frozen.get("top_map_header_sha256") != sha256(
                root / "src/generated/joint_pair_top_map.h"):
        parser.error("bounded-top design base changed")
    frozen = json.loads(base_pair_design.read_text())
    zero_design = folder / "joint-window4-zero-design.json"
    zero_inputs = folder / "joint-window4-zero-inputs/inputs.json"
    if frozen.get("base_zero_design_sha256") != sha256(zero_design) or \
            frozen.get("training_inputs_sha256") != sha256(zero_inputs) or \
            frozen.get("source_sha256") != sha256(folder / "make_joint_pair_design.py") or \
            frozen.get("map_producer_sha256") != sha256(folder / "make_joint_pair_map.py") or \
            frozen.get("map_header_sha256") != sha256(root / "src/generated/joint_pair_map.h"):
        parser.error("pair design base changed")
    zero_frozen = json.loads(zero_design.read_text())
    plane_design = folder / "joint-window4-plane-design.json"
    plane_inputs = folder / "joint-window4-plane-inputs/inputs.json"
    if zero_frozen.get("base_plane_design_sha256") != sha256(plane_design) or \
            zero_frozen.get("training_inputs_sha256") != sha256(plane_inputs):
        parser.error("zero-window design base changed")
    plane_frozen = json.loads(plane_design.read_text())
    hot_design = folder / "joint-window4-hot-design.json"
    if plane_frozen.get("base_hot_design_sha256") != sha256(hot_design) or \
            plane_frozen.get("base_hot_map_sha256") != sha256(
                root / "src/generated/joint_window4_hot.h"):
        parser.error("plane design base changed")
    if json.loads(hot_design.read_text()).get("training_inputs_sha256") != \
            sha256(folder / "joint-window4-inputs/inputs.json"):
        parser.error("hot design training fixture changed")
    for fixture_name, expected_hash in inputs["prior_manifest_sha256"].items():
        prior_manifest = folder / fixture_name
        if sha256(prior_manifest) != expected_hash:
            parser.error("prior manifest changed: " + fixture_name)
        artifacts.append(prior_manifest)
        prior = json.loads(prior_manifest.read_text())
        for prior_case in prior["cases"]:
            prior_file = prior_manifest.parent / prior_case["scalar_file"]
            if sha256(prior_file) != prior_case["scalar_file_sha256"]:
                parser.error("prior scalar file changed")
            artifacts.append(prior_file)
    cases = []
    for case in inputs["cases"]:
        scalar_file = inputs_path.parent / case["scalar_file"]
        if sha256(scalar_file) != case["scalar_file_sha256"]:
            parser.error("scalar-file hash differs for " + case["id"])
        artifacts.append(scalar_file)
        point_index = case["id"].rsplit("point", 1)[1]
        common = [case["curve"]["name"], point_index, str(scalar_file)]
        control = native_rows[(case["id"], args.reference_mode)]
        candidate = native_rows[(case["id"], "joint-pair-top-pos")]
        if not control.get("gate_pass") or not candidate.get("gate_pass"):
            parser.error("native panel rejected " + case["id"])
        fields = control["fields"]
        if any(fields.get(field) != candidate["fields"].get(field) for field in pair_fields):
            parser.error("native paired fields differ for " + case["id"])
        if fields["curve"] != case["curve"]["name"] or fields["point_index"] != point_index or \
                fields["count"] != str(case["count"]) or fields["base_x"] != case["base_x"] or \
                fields["base_y"] != case["base_y"]:
            parser.error("native panel differs from frozen fixture for " + case["id"])
        cases.append({"id": case["id"],
                      "reference": [str(args.binary), args.reference_mode] + common,
                      "candidate": [str(args.binary), "joint-pair-top-pos"] + common,
                      "expected_fields": {field: fields[field] for field in pair_fields},
                      "expected_result": fields["output_digest"]})
    artifacts = sorted(set(artifacts), key=str)
    if len(cases) != 8 or any(not path.is_file() for path in artifacts):
        parser.error("a case, source, build, or fixture artifact is missing")
    manifest = {
        "schema": 1, "name": "joint-pair-top-vs-" + args.reference_mode,
        "workdir": str(root),
        "isolation": {"cgroup": str(args.cgroup), "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_nodes},
        "build": {"binary_sha256": sha256(args.binary),
                  "same_binary_for_both_modes": True,
                  "reference_mode": args.reference_mode,
                  "candidate_mode": "joint-pair-top-pos"},
        "fixture": {"design_sha256": sha256(design), "inputs_sha256": sha256(inputs_path),
                    "native_panel_sha256": sha256(native_panel),
                    "case_count": len(cases), "scalars_per_case": 4096},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s, "repetitions": args.repetitions,
        "measurement_boundary": "bench.c online_ms: sequential scalar multiplications over one frozen 4096-scalar case, after input loading and point-table preparation, before independent scalar replay; result is batch latency, not one-target DLP latency",
        "pair_fields": pair_fields, "result_field": "output_digest", "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "pairs": len(cases) * args.repetitions,
                      "manifest_sha256": sha256(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
