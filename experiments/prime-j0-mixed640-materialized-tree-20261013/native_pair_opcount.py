#!/usr/bin/env python3
"""Instrument the existing mixed-640 grouped reference on the same holdout."""

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
    spec = importlib.util.spec_from_file_location("mixed640_opcount_overlay", HERE / "native_opcount.py")
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    overlay.main(target)
    source = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    body = source.read_text()
    statics = (
        "#[cfg(test)] static MIXED640_BASE_ROTATIONS: std::sync::atomic::AtomicUsize =\n"
        "    std::sync::atomic::AtomicUsize::new(0);\n"
        "#[cfg(test)] static MIXED640_BASE_OPS_TOTAL: std::sync::atomic::AtomicUsize =\n"
        "    std::sync::atomic::AtomicUsize::new(0);\n"
        "#[cfg(test)] static MIXED640_BASE_ROT_TOTAL: std::sync::atomic::AtomicUsize =\n"
        "    std::sync::atomic::AtomicUsize::new(0);\n"
    )
    body = once(body, "fn u256_mul_const_solinas(value: super::U256, constant: super::U256) -> super::U256 {",
        statics + "fn u256_mul_const_solinas(value: super::U256, constant: super::U256) -> super::U256 {\n"
        "    #[cfg(test)] if MIXED640_JOIN_ACTIVE.load(std::sync::atomic::Ordering::Relaxed) {\n"
        "        MIXED640_BASE_ROTATIONS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n"
        "    }")
    marker = "pub(super) fn multiply_u256_tau_mixed_radix640_gauge_xyzz_tau("
    before, after = body.split(marker, 1)
    after = once(after,
        '    assert!(a.is_zero() && b.is_zero(), "mixed-radix 640 recoding did not terminate");\n\n'
        '    let mut buckets = [U256XYZZ::identity(); 2];',
        '    assert!(a.is_zero() && b.is_zero(), "mixed-radix 640 recoding did not terminate");\n\n'
        '    #[cfg(test)] {\n'
        '        MIXED640_JOIN_OPS.store(0, std::sync::atomic::Ordering::Relaxed);\n'
        '        MIXED640_BASE_ROTATIONS.store(0, std::sync::atomic::Ordering::Relaxed);\n'
        '        MIXED640_JOIN_ACTIVE.store(true, std::sync::atomic::Ordering::Relaxed);\n'
        '    }\n'
        '    let mut buckets = [U256XYZZ::identity(); 2];')
    after = once(after,
        '    let point = buckets[0].add_xyzz(buckets[1].tau()).affine_hex_binary_inverse();',
        '    let joined = buckets[0].add_xyzz(buckets[1].tau());\n'
        '    #[cfg(test)] MIXED640_JOIN_ACTIVE.store(false, std::sync::atomic::Ordering::Relaxed);\n'
        '    let point = joined.affine_hex_binary_inverse();')
    body = before + marker + after
    needle = (
        '            assert_eq!(candidate.0, case["point_hex"].as_str().unwrap(),\n'
        '                       "frozen affine point {index}");'
    )
    replacement = needle + (
        '\n            let baseline = multiply_u256_tau_mixed_radix640_gauge_xyzz_tau(words);\n'
        '            assert_eq!(baseline.0, candidate.0, "paired native point {index}");\n'
        '            let generic = MIXED640_JOIN_OPS.load(std::sync::atomic::Ordering::Relaxed);\n'
        '            let rotations = MIXED640_BASE_ROTATIONS.load(std::sync::atomic::Ordering::Relaxed);\n'
        '            assert_eq!(rotations, baseline.6, "rotation count {index}");\n'
        '            MIXED640_BASE_OPS_TOTAL.fetch_add(generic, std::sync::atomic::Ordering::Relaxed);\n'
        '            MIXED640_BASE_ROT_TOTAL.fetch_add(rotations, std::sync::atomic::Ordering::Relaxed);'
    )
    body = once(body, needle, replacement)
    body = once(body,
        '                 cases.len(), MIXED640_HOLDOUT_OPS.load(std::sync::atomic::Ordering::Relaxed));',
        '                 cases.len(), MIXED640_HOLDOUT_OPS.load(std::sync::atomic::Ordering::Relaxed));\n'
        '        println!("mixed640_reference_generic_calls={} solinas_rotations={}",\n'
        '                 MIXED640_BASE_OPS_TOTAL.load(std::sync::atomic::Ordering::Relaxed),\n'
        '                 MIXED640_BASE_ROT_TOTAL.load(std::sync::atomic::Ordering::Relaxed));')
    source.write_text(body)
    receipt = {"schema": 1,
               "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "generated_module_sha256": sha256(source.read_bytes()).hexdigest()}
    (target / "native-pair-opcount-overlay.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]).resolve())
