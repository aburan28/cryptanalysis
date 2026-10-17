#!/usr/bin/env python3
"""Freeze a serial same-fixture panel for packed x and gauge-class layers."""

from hashlib import sha256
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "prime-j0-affine-uniform-20261015"
PREFIX = "/workspace/bench-sources/"
BASELINE = PREFIX + "prime-j0-affine-uniform-native/"
PACKED = PREFIX + "prime-j0-eisenstein-packed-native/"
GAUGE = PREFIX + "prime-j0-eisenstein-gauge-native/"

HASHES = {
    "baseline_binary": "44a6b7f0d9e1460e55da985e4e122c2b5d36fc384b9ead7ecdafeb4756350434",
    "packed_binary": "60f282f5ce2b730440bb8ab0ca747ea1184dd2405b448ad8971a1d03362dfd31",
    "packed_front": "2b26dc2b5ddcf06800e3dd7109d6e167306bdfa4743dc63ef6f29fa185016df3",
    "packed_windows": "7b7f6eff42dc9e7197b8c6c30d3792ebc18e6f17443e8944fc5fe0d3452117ca",
    "gauge_binary": "f0a60937e9af8efae3b3572929be51f411d1d56bb53dee97ef0a0d8b17593874",
    "gauge_front": "5ef632cd74ea7bc3ec38ce7b815481bf91cd56e8d2444621e1d010a95ea8edee",
    "gauge_windows": "3650b42e1ff33c761efd7fd73a3dac4c12a21111afe5fbc8ac73b4e0782557bd",
}


def canonical(data):
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def main():
    original = json.loads((BASE / "tier1-affine-uniform-cpu40-manifest.json").read_text())
    expected = original["cases"][0]["expected_fields"]
    point = original["cases"][0]["expected_result"]
    baseline_cmd = [BASELINE + "target/release/eisenstein_fixed",
                    "--benchmark-split-prime-affine-two-x-uniform", "128", "96"]
    packed_cmd = [PACKED + "target/release/eisenstein_fixed",
                  "--benchmark-split-prime-packed-x-uniform", "128", "96"]
    gauge_cmd = [GAUGE + "target/release/eisenstein_fixed",
                 "--benchmark-split-prime-gauge-layer-uniform", "128", "96"]
    manifest = {key: value for key, value in original.items() if key not in ("cases", "artifacts")}
    manifest["cases"] = [
        {"id": name, "reference": baseline_cmd, "candidate": candidate,
         "expected_fields": expected, "expected_result": point}
        for name, candidate in (
            ("cal_before", baseline_cmd),
            ("compare_packed", packed_cmd),
            ("compare_gauge", gauge_cmd),
            ("cal_after", baseline_cmd),
        )
    ]
    extra = []
    for prefix, overlay, build, replay in (
        (PACKED, "native_packed_x_overlay.py", "packed-build.stderr", "packed-full-replay.stdout"),
        (GAUGE, "native_gauge_layer_overlay.py", "gauge-build.stderr", "gauge-full-replay.stdout"),
    ):
        extra.extend(prefix + item for item in (
            "Cargo.lock", "Cargo.toml", overlay, build, replay,
            "src/bin/eisenstein_fixed.rs", "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
            "src/bin/mixed640_uniform_fixture.json", "target/release/eisenstein_fixed",
        ))
    manifest["artifacts"] = sorted(set(original["artifacts"] + extra))
    manifest["measurement_boundary"] = original["measurement_boundary"]
    rules = {
        "schema": 1,
        "tier": "tier1_instance",
        "purpose": "same-point 12288-scalar full radix-14 batch path: 65-byte packed Eisenstein x and class-gauge affine sum against full two-x reference",
        "repetitions": 16,
        "case_order": [case["id"] for case in manifest["cases"]],
        "arm_order": "A/A, packed comparison, gauge comparison, A/A; runner alternates reference and candidate per repeat",
        "aa_acceptance": [0.90, 1.11],
        "comparison_acceptance": "all 16 pairs per candidate valid, adjacent A/A gates pass, paired bootstrap 95% log-ratio interval excludes one",
        "fixture_sha256": expected["fixture_sha256"],
        "timing_boundary": manifest["measurement_boundary"],
        "execution_cpu": 40,
        "service_cpu": 2,
        "hashes": HASHES,
        "overlay_sha256": {
            name: sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("native_packed_x_overlay.py", "native_gauge_layer_overlay.py")
        },
    }
    (ROOT / "tier1-eisenstein-packed-gauge-cpu40-manifest.json").write_text(canonical(manifest))
    (ROOT / "tier1-eisenstein-packed-gauge-cpu40-rules.json").write_text(canonical(rules))


if __name__ == "__main__":
    main()
