#!/usr/bin/env python3
"""Instrument actual field-wrapper calls in a disposable native test crate."""

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
    counters = (
        "#[cfg(test)]\n"
        "static MIXED640_JOIN_ACTIVE: std::sync::atomic::AtomicBool =\n"
        "    std::sync::atomic::AtomicBool::new(false);\n"
        "#[cfg(test)]\n"
        "static MIXED640_JOIN_OPS: std::sync::atomic::AtomicUsize =\n"
        "    std::sync::atomic::AtomicUsize::new(0);\n"
        "#[cfg(test)]\n"
        "static MIXED640_HOLDOUT_OPS: std::sync::atomic::AtomicUsize =\n"
        "    std::sync::atomic::AtomicUsize::new(0);\n\n"
    )
    body = once(body, "fn u256_mul(a: super::U256, b: super::U256) -> super::U256 {",
                counters + "fn u256_mul(a: super::U256, b: super::U256) -> super::U256 {\n"
                "    #[cfg(test)] if MIXED640_JOIN_ACTIVE.load(std::sync::atomic::Ordering::Relaxed) {\n"
                "        MIXED640_JOIN_OPS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n"
                "    }")
    body = once(body, "fn u256_square(a: super::U256) -> super::U256 {",
                "fn u256_square(a: super::U256) -> super::U256 {\n"
                "    #[cfg(test)] if MIXED640_JOIN_ACTIVE.load(std::sync::atomic::Ordering::Relaxed) {\n"
                "        MIXED640_JOIN_OPS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n"
                "    }")
    body = once(body,
        "    if selected.is_empty() { return U256XYZZ::identity(); }\n    while selected.len() > 1 {",
        "    if selected.is_empty() { return U256XYZZ::identity(); }\n"
        "    #[cfg(test)] {\n"
        "        MIXED640_JOIN_OPS.store(0, std::sync::atomic::Ordering::Relaxed);\n"
        "        MIXED640_JOIN_ACTIVE.store(true, std::sync::atomic::Ordering::Relaxed);\n"
        "    }\n    while selected.len() > 1 {")
    body = once(body, "    match selected[0] {\n        Mixed640TreeNode::Affine(p)",
                "    #[cfg(test)] MIXED640_JOIN_ACTIVE.store(false, std::sync::atomic::Ordering::Relaxed);\n"
                "    match selected[0] {\n        Mixed640TreeNode::Affine(p)")
    body = once(body,
        "            let candidate = multiply_u256_tau_mixed640_pretau_tree(words);\n"
        "            assert_eq!(candidate.0, case[\"point_hex\"].as_str().unwrap(),",
        "            let candidate = multiply_u256_tau_mixed640_pretau_tree(words);\n"
        "            let n = candidate.2 + 1;\n"
        "            let expected_calls = if n < 2 { 0 } else { 10 * n - 14 };\n"
        "            let actual_calls = MIXED640_JOIN_OPS.load(std::sync::atomic::Ordering::Relaxed);\n"
        "            assert_eq!(actual_calls, expected_calls, \"join calls {index}\");\n"
        "            MIXED640_HOLDOUT_OPS.fetch_add(actual_calls, std::sync::atomic::Ordering::Relaxed);\n"
        "            assert_eq!(candidate.0, case[\"point_hex\"].as_str().unwrap(),")
    body = once(body,
        '        println!("mixed640_pretau_holdout_cases={} status=verified", cases.len());',
        '        println!("mixed640_pretau_holdout_cases={} status=verified join_calls={}",\n'
        '                 cases.len(), MIXED640_HOLDOUT_OPS.load(std::sync::atomic::Ordering::Relaxed));')
    source.write_text(body)
    receipt = {"schema": 1, "base_overlay_sha256": sha256((HERE / "native_overlay.py").read_bytes()).hexdigest(),
               "instrumentation_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "generated_module_sha256": sha256(source.read_bytes()).hexdigest()}
    (target / "native-opcount-overlay.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]).resolve())
