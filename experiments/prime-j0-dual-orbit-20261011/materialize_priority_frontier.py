#!/usr/bin/env python3
"""Add a same-panel three-image control to the priority native test."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "priority_frontier_parent", HERE / "materialize_priority_native.py")
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
WINDOW_SOURCE = "src/bin/eisenstein_fixed/unit_orbit_windows.rs"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def once(source, old, new):
    assert source.count(old) == 1, (old[:100], source.count(old))
    return source.replace(old, new)


def main():
    assert len(sys.argv) == 2, "usage: materialize_priority_frontier.py OUTPUT_DIRECTORY"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    subprocess.run([sys.executable, str(HERE / "materialize_priority_native.py"),
                    str(output)], check=True, capture_output=True)
    parent_raw = (output / "materialization.json").read_bytes()
    parent = json.loads(parent_raw)
    window = output / WINDOW_SOURCE
    source = window.read_text()
    start = source.index("    fn dual_rho0_folded_matches_fresh_panel_and_controls() {")
    end = source.index("    #[test]\n    fn fused_orbit_matches", start)
    test = source[start:end]
    test = once(test, "        let mut fused_rotations = 0usize;",
        "        let mut fused_rotations = 0usize;\n"
        "        let mut tau_only_additions = 0usize;\n"
        "        let mut tau_only_rotations = 0usize;")
    test = once(test,
        "            let fused = multiply_u256_tau_fused_orbit_gauge_xyzz_tau(words);",
        "            let fused = multiply_u256_tau_fused_orbit_gauge_xyzz_tau(words);\n"
        "            let tau_only = multiply_u256_tau_power2_tau2_gauge_xyzz_tau(words);")
    test = once(test,
        '            assert_eq!(candidate.0, fused.0, "fused point {index}");',
        '            assert_eq!(candidate.0, fused.0, "fused point {index}");\n'
        '            assert_eq!(candidate.0, tau_only.0, "three-image point {index}");')
    test = once(test,
        "            fused_rotations += fused.6;",
        "            fused_rotations += fused.6;\n"
        "            tau_only_additions += tau_only.2;\n"
        "            tau_only_rotations += tau_only.6;")
    test = once(test,
        '        assert_eq!(fused_additions, 49_152);',
        '        assert_eq!(fused_additions, 49_152);\n'
        '        assert_eq!(tau_only_additions, 49_152);')
    test = once(test,
        '                 fused_additions, fused_rotations);',
        '                 fused_additions, fused_rotations);\n'
        '        println!("priority_three_image_cases={} retained_bytes={} additions={} gauge_products={}",\n'
        '                 scalars.len(), warm_format(61), tau_only_additions, tau_only_rotations);')
    source = source[:start] + test + source[end:]
    window.write_text(source)
    receipt = {"schema": 1, "timing_class": "correctness_and_operation_counts_only",
               "materializer_sha256": digest(Path(__file__)),
               "parent_materialization_sha256": sha256(parent_raw).hexdigest(),
               "generated_sha256": {name: digest(output / name)
                                    for name in parent["generated_sha256"]},
               "assets_sha256": parent["assets_sha256"]}
    (output / "materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"generated_sha256": receipt["generated_sha256"],
                      "assets_sha256": receipt["assets_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
