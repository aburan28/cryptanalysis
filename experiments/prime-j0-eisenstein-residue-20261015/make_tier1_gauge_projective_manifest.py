#!/usr/bin/env python3
"""Freeze gauge affine versus projective class-join on identical scalar streams."""

from hashlib import sha256
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
GAUGE = "/workspace/bench-sources/prime-j0-eisenstein-gauge-native/"
PROJECTIVE = "/workspace/bench-sources/prime-j0-eisenstein-gauge-projective-native/"
RULES_PATH = "/workspace/isolated-bench/panels/tier1-eisenstein-gauge-projective-cpu40-rules.json"

HASHES = {
    "gauge_binary": "f0a60937e9af8efae3b3572929be51f411d1d56bb53dee97ef0a0d8b17593874",
    "gauge_front": "5ef632cd74ea7bc3ec38ce7b815481bf91cd56e8d2444621e1d010a95ea8edee",
    "gauge_windows": "3650b42e1ff33c761efd7fd73a3dac4c12a21111afe5fbc8ac73b4e0782557bd",
    "projective_binary": "7db95bf8adeda3c907e7b3c24420041397916a6a8e6c5fa5dae288e50003fdde",
    "projective_front": "8b1eefde25f2e3881611ef31d1333d11a76c4e854f002de880fe19f7b83377f4",
    "projective_windows": "9b103346a8bb5a4594c0f26fc073a9dc92faa7121d4c97a71b0e7944a258bdb9",
}


def canonical(data):
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def main():
    previous = json.loads((ROOT / "tier1-eisenstein-packed-gauge-cpu40-manifest.json").read_text())
    expected = previous["cases"][0]["expected_fields"]
    result = previous["cases"][0]["expected_result"]
    gauge_cmd = [GAUGE + "target/release/eisenstein_fixed",
                 "--benchmark-split-prime-gauge-layer-uniform", "128", "96"]
    projective_cmd = [PROJECTIVE + "target/release/eisenstein_fixed",
                      "--benchmark-split-prime-gauge-projective-uniform", "128", "96"]
    manifest = {k: v for k, v in previous.items() if k not in ("cases", "artifacts")}
    manifest["cases"] = [
        {"id": name, "reference": gauge_cmd, "candidate": candidate,
         "expected_fields": expected, "expected_result": result}
        for name, candidate in (("cal_before", gauge_cmd),
                                ("compare", projective_cmd),
                                ("cal_after", gauge_cmd))
    ]
    artifacts = [a for a in previous["artifacts"]
                 if not a.startswith("/workspace/bench-sources/prime-j0-affine-uniform-native/")
                 and not a.startswith("/workspace/bench-sources/prime-j0-eisenstein-packed-native/")]
    for prefix, overlay, build, replay in (
        (PROJECTIVE, "native_gauge_projective_overlay.py",
         "gauge-projective-build.stderr", "gauge-projective-full-replay.stdout"),
    ):
        artifacts.extend(prefix + suffix for suffix in (
            "Cargo.toml", "Cargo.lock", overlay, build, replay,
            "src/bin/eisenstein_fixed.rs", "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
            "src/bin/mixed640_uniform_fixture.json", "target/release/eisenstein_fixed"))
    artifacts.append(RULES_PATH)
    manifest["artifacts"] = sorted(set(artifacts))
    rules = {
        "schema": 1, "tier": "tier1_instance", "repetitions": 16,
        "purpose": "same-point 12288-scalar radix-14 stream: affine versus projective join of three gauge-class sums",
        "case_order": [case["id"] for case in manifest["cases"]],
        "aa_acceptance": [0.90, 1.11],
        "comparison_acceptance": "all 16 pairs valid, both adjacent A/A controls pass, paired bootstrap 95% log-ratio interval excludes one",
        "execution_cpu": 40, "service_cpu": 2,
        "fixture_sha256": expected["fixture_sha256"],
        "timing_boundary": manifest["measurement_boundary"],
        "hashes": HASHES,
        "overlay_sha256": sha256((ROOT / "native_gauge_projective_overlay.py").read_bytes()).hexdigest(),
    }
    (ROOT / "tier1-eisenstein-gauge-projective-cpu40-rules.json").write_text(canonical(rules))
    (ROOT / "tier1-eisenstein-gauge-projective-cpu40-manifest.json").write_text(canonical(manifest))


if __name__ == "__main__":
    main()
