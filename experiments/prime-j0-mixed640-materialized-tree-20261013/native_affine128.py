#!/usr/bin/env python3
"""Prepare a 128-byte plain/tau affine pair table for the pre-tau tree."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def once(body, old, new):
    assert body.count(old) == 1, old[:90]
    return body.replace(old, new, 1)


def main(target):
    spec = importlib.util.spec_from_file_location("mixed640_native_overlay", HERE / "native_overlay.py")
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    overlay.prepare(target)
    source = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    body = source.read_text()
    marker = "// Inserted into the pinned mixed-radix 640 module by native_overlay.py."
    before, variant = body.split(marker, 1)
    pair = (
        "#[derive(Clone, Copy)]\n"
        "struct Mixed640AffinePair {\n"
        "    plain: U256Affine,\n"
        "    tau: U256Affine,\n"
        "}\n\n"
        "impl Mixed640AffinePair {\n"
        "    fn select(self, exponent: usize, unit_code: usize) -> U256Affine {\n"
        "        assert!(exponent < 2);\n"
        "        let point = if exponent == 0 { self.plain } else { self.tau };\n"
        "        point.unit_solinas(unit_code)\n"
        "    }\n"
        "}\n\n"
    )
    variant = once(variant, "struct Mixed640PreTauTables {", pair + "struct Mixed640PreTauTables {")
    variant = variant.replace("U256TwoXOrbitTauPair", "Mixed640AffinePair")
    variant = once(variant,
                   "fn mixed640_materialize(point: U256Affine) -> U256TwoXAffine {\n"
                   "    U256TwoXAffine::from_affine(point)\n"
                   "}\n\n", "")
    variant = once(variant, "plain: mixed640_materialize(plain),", "plain,")
    variant = once(variant, "tau: mixed640_materialize(tau),", "tau,")
    variant = once(variant, "assert_eq!(size_of::<Mixed640AffinePair>(), 192);",
                   "assert_eq!(size_of::<Mixed640AffinePair>(), 128);")
    variant = once(variant,
        "            let candidate = multiply_u256_tau_mixed640_pretau_tree(words);\n"
        "            assert_eq!(candidate.0, case[\"point_hex\"].as_str().unwrap(),",
        "            let candidate = multiply_u256_tau_mixed640_pretau_tree(words);\n"
        "            if index == 0 { println!(\"mixed640_affine128_retained_bytes={}\", candidate.3); }\n"
        "            assert_eq!(candidate.0, case[\"point_hex\"].as_str().unwrap(),")
    source.write_text(before + marker + variant)
    receipt = {"schema": 1,
               "base_overlay_sha256": sha256((HERE / "native_overlay.py").read_bytes()).hexdigest(),
               "affine_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "generated_module_sha256": sha256(source.read_bytes()).hexdigest(),
               "point_payload_bytes": 415190 * 128,
               "point_and_atlas_bytes": 415190 * 128 + 4729980}
    (target / "native-affine128-overlay.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]).resolve())
