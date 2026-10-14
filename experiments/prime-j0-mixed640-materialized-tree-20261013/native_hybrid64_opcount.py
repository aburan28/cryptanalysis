#!/usr/bin/env python3
"""Count native tree field calls and selected-tau Solinas rotations."""

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
    spec = importlib.util.spec_from_file_location("mixed640_hybrid_overlay", HERE / "native_hybrid64.py")
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    overlay.main(target)
    source = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    body = source.read_text()
    counters = (
        "#[cfg(test)] static HYBRID64_SELECT_ACTIVE: std::sync::atomic::AtomicBool =\n"
        "    std::sync::atomic::AtomicBool::new(false);\n"
        "#[cfg(test)] static HYBRID64_JOIN_ACTIVE: std::sync::atomic::AtomicBool =\n"
        "    std::sync::atomic::AtomicBool::new(false);\n"
        "#[cfg(test)] static HYBRID64_SELECT_ROTATIONS: std::sync::atomic::AtomicUsize =\n"
        "    std::sync::atomic::AtomicUsize::new(0);\n"
        "#[cfg(test)] static HYBRID64_JOIN_CALLS: std::sync::atomic::AtomicUsize =\n"
        "    std::sync::atomic::AtomicUsize::new(0);\n"
        "#[cfg(test)] static HYBRID64_ROT_TOTAL: std::sync::atomic::AtomicUsize =\n"
        "    std::sync::atomic::AtomicUsize::new(0);\n"
        "#[cfg(test)] static HYBRID64_JOIN_TOTAL: std::sync::atomic::AtomicUsize =\n"
        "    std::sync::atomic::AtomicUsize::new(0);\n"
    )
    body = once(body, "fn u256_mul(a: super::U256, b: super::U256) -> super::U256 {",
        counters + "fn u256_mul(a: super::U256, b: super::U256) -> super::U256 {\n"
        "    #[cfg(test)] if HYBRID64_JOIN_ACTIVE.load(std::sync::atomic::Ordering::Relaxed) {\n"
        "        HYBRID64_JOIN_CALLS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n"
        "    }")
    body = once(body, "fn u256_square(a: super::U256) -> super::U256 {",
        "fn u256_square(a: super::U256) -> super::U256 {\n"
        "    #[cfg(test)] if HYBRID64_JOIN_ACTIVE.load(std::sync::atomic::Ordering::Relaxed) {\n"
        "        HYBRID64_JOIN_CALLS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n"
        "    }")
    body = once(body,
        "fn u256_mul_const_solinas(value: super::U256, constant: super::U256) -> super::U256 {",
        "fn u256_mul_const_solinas(value: super::U256, constant: super::U256) -> super::U256 {\n"
        "    #[cfg(test)] if HYBRID64_SELECT_ACTIVE.load(std::sync::atomic::Ordering::Relaxed) {\n"
        "        HYBRID64_SELECT_ROTATIONS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n"
        "    }")
    body = once(body, "        else { self.tau.unit_solinas(unit_code) }",
        "        else {\n"
        "            #[cfg(test)] HYBRID64_SELECT_ACTIVE.store(true, std::sync::atomic::Ordering::Relaxed);\n"
        "            let point = self.tau.unit_solinas(unit_code);\n"
        "            #[cfg(test)] HYBRID64_SELECT_ACTIVE.store(false, std::sync::atomic::Ordering::Relaxed);\n"
        "            point\n"
        "        }")
    body = once(body,
        "    if selected.is_empty() { return U256XYZZ::identity(); }\n    while selected.len() > 1 {",
        "    if selected.is_empty() { return U256XYZZ::identity(); }\n"
        "    #[cfg(test)] {\n"
        "        HYBRID64_JOIN_CALLS.store(0, std::sync::atomic::Ordering::Relaxed);\n"
        "        HYBRID64_JOIN_ACTIVE.store(true, std::sync::atomic::Ordering::Relaxed);\n"
        "    }\n    while selected.len() > 1 {")
    body = once(body, "    match selected[0] {\n        Mixed640TreeNode::Affine(p)",
        "    #[cfg(test)] HYBRID64_JOIN_ACTIVE.store(false, std::sync::atomic::Ordering::Relaxed);\n"
        "    match selected[0] {\n        Mixed640TreeNode::Affine(p)")
    body = once(body,
        "    let mut selected = Vec::with_capacity(RADIX640_SCHEDULE.len());",
        "    #[cfg(test)] HYBRID64_SELECT_ROTATIONS.store(0, std::sync::atomic::Ordering::Relaxed);\n"
        "    let mut selected = Vec::with_capacity(RADIX640_SCHEDULE.len());")
    body = once(body,
        '            if index == 0 { println!("mixed640_hybrid64_retained_bytes={}", candidate.3); }',
        '            if index == 0 { println!("mixed640_hybrid64_retained_bytes={}", candidate.3); }\n'
        '            let n = candidate.2 + 1;\n'
        '            let expected_calls = if n < 2 { 0 } else { 10 * n - 14 };\n'
        '            let actual_calls = HYBRID64_JOIN_CALLS.load(std::sync::atomic::Ordering::Relaxed);\n'
        '            assert_eq!(actual_calls, expected_calls, "join calls {index}");\n'
        '            HYBRID64_JOIN_TOTAL.fetch_add(actual_calls, std::sync::atomic::Ordering::Relaxed);\n'
        '            HYBRID64_ROT_TOTAL.fetch_add(\n'
        '                HYBRID64_SELECT_ROTATIONS.load(std::sync::atomic::Ordering::Relaxed),\n'
        '                std::sync::atomic::Ordering::Relaxed);')
    body = once(body,
        '        println!("mixed640_pretau_holdout_cases={} status=verified", cases.len());',
        '        println!("mixed640_pretau_holdout_cases={} status=verified join_calls={} tau_rotations={}",\n'
        '                 cases.len(),\n'
        '                 HYBRID64_JOIN_TOTAL.load(std::sync::atomic::Ordering::Relaxed),\n'
        '                 HYBRID64_ROT_TOTAL.load(std::sync::atomic::Ordering::Relaxed));')
    source.write_text(body)
    receipt = {"schema": 1, "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "generated_module_sha256": sha256(source.read_bytes()).hexdigest()}
    (target / "native-hybrid64-opcount-overlay.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]).resolve())
