#!/usr/bin/env python3
"""Apply frozen window/exponent orbit gauges to the 128-byte table."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def once(body, old, new):
    assert body.count(old) == 1, old[:100]
    return body.replace(old, new, 1)


def main(target):
    spec = importlib.util.spec_from_file_location("mixed640_affine_overlay", HERE / "native_affine128.py")
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    overlay.main(target)
    policy = json.loads((HERE / "gauge-policy.json").read_text())
    assert policy["status"] == "training_only_window_exponent_gauge"
    assert len(policy["gauges"]) == 14
    assert all(len(row) == 2 and all(g in (0, 1, 2) for g in row)
               for row in policy["gauges"])
    source = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    body = source.read_text()
    marker = "// Inserted into the pinned mixed-radix 640 module by native_overlay.py."
    before, variant = body.split(marker, 1)
    gauge_rows = ",\n    ".join(f"[{a}, {b}]" for a, b in policy["gauges"])
    variant = once(variant, "#[derive(Clone, Copy)]\nstruct Mixed640AffinePair {",
        f"const MIXED640_GAUGES: [[usize; 2]; 14] = [\n    {gauge_rows}\n];\n\n"
        "#[derive(Clone, Copy)]\nstruct Mixed640AffinePair {")
    variant = once(variant,
        "fn select(self, exponent: usize, unit_code: usize) -> U256Affine {",
        "fn select(self, exponent: usize, unit_code: usize, gauge: usize) -> U256Affine {")
    variant = once(variant,
        "        point.unit_solinas(unit_code)",
        "        assert!(gauge < 3 && unit_code < 6);\n"
        "        let adjusted_power = (unit_code / 2 + 3 - gauge) % 3;\n"
        "        point.unit_solinas(2 * adjusted_power + (unit_code & 1))")
    variant = once(variant,
        "                .map(|(plain, tau)| Mixed640AffinePair {\n"
        "                    plain,\n"
        "                    tau,\n"
        "                }).collect::<Vec<_>>().into_boxed_slice());",
        "                .map(|(plain, tau)| Mixed640AffinePair {\n"
        "                    plain: plain.unit_solinas(2 * MIXED640_GAUGES[index][0]),\n"
        "                    tau: tau.unit_solinas(2 * MIXED640_GAUGES[index][1]),\n"
        "                }).collect::<Vec<_>>().into_boxed_slice());")
    variant = once(variant,
        "tables.windows[index][seed_id].select(exponent, unit_code)",
        "tables.windows[index][seed_id].select(exponent, unit_code, MIXED640_GAUGES[index][exponent])")
    variant = variant.replace("mixed640_affine128_retained_bytes", "mixed640_gauge128_retained_bytes")
    source.write_text(before + marker + variant)
    receipt = {"schema": 1,
               "gauge_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "policy_sha256": sha256((HERE / "gauge-policy.json").read_bytes()).hexdigest(),
               "generated_module_sha256": sha256(source.read_bytes()).hexdigest(),
               "point_and_atlas_bytes": 415190 * 128 + 4729980}
    (target / "native-gauge128-overlay.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]).resolve())
