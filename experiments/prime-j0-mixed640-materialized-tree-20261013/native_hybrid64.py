#!/usr/bin/env python3
"""Replace the 192-byte paired table with a 160-byte plain/tau entry."""

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
        "struct Mixed640HybridEntry {\n"
        "    plain: U256TwoXAffine,\n"
        "    tau: U256Affine,\n"
        "}\n\n"
        "impl Mixed640HybridEntry {\n"
        "    fn select(self, exponent: usize, unit_code: usize) -> U256Affine {\n"
        "        assert!(exponent < 2);\n"
        "        if exponent == 0 { self.plain.unit(unit_code) }\n"
        "        else { self.tau.unit_solinas(unit_code) }\n"
        "    }\n"
        "}\n\n"
    )
    variant = once(variant, "struct Mixed640PreTauTables {", pair + "struct Mixed640PreTauTables {")
    variant = variant.replace("U256TwoXOrbitTauPair", "Mixed640HybridEntry")
    variant = once(variant, "tau: mixed640_materialize(tau),", "tau,")
    variant = once(variant, "assert_eq!(size_of::<Mixed640HybridEntry>(), 192);",
                   "assert_eq!(size_of::<Mixed640HybridEntry>(), 160);")
    variant = once(variant,
        "            let candidate = multiply_u256_tau_mixed640_pretau_tree(words);\n"
        "            assert_eq!(candidate.0, case[\"point_hex\"].as_str().unwrap(),",
        "            let candidate = multiply_u256_tau_mixed640_pretau_tree(words);\n"
        "            if index == 0 { println!(\"mixed640_hybrid64_retained_bytes={}\", candidate.3); }\n"
        "            assert_eq!(candidate.0, case[\"point_hex\"].as_str().unwrap(),")
    body = before + marker + variant
    source.write_text(body)
    receipt = {"schema": 1,
               "base_overlay_sha256": sha256((HERE / "native_overlay.py").read_bytes()).hexdigest(),
               "hybrid_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "generated_module_sha256": sha256(source.read_bytes()).hexdigest(),
               "point_payload_bytes": 415190 * 160,
               "point_and_atlas_bytes": 415190 * 160 + 4729980}
    (target / "native-hybrid64-overlay.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]).resolve())
