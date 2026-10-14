#!/usr/bin/env python3
"""Build a disposable Solinas-kernel counter for the frozen low-work evaluator."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import native_overlay_workdepth as parent

HERE = Path(__file__).resolve().parent


def replace_once(body: str, old: str, new: str) -> str:
    assert body.count(old) == 1, old[:100]
    return body.replace(old, new, 1)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def prepare(target: Path) -> dict:
    target = target.resolve()
    record = parent.prepare(target)
    module = target / "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    body = module.read_text()
    anchor = "fn u256_mul_solinas_with<const KARATSUBA: bool>(\n    value: super::U256, constant: super::U256,\n) -> super::U256 {\n"
    inserted = ("static HEX_SOLINAS_COUNT: std::sync::atomic::AtomicUsize = "
                "std::sync::atomic::AtomicUsize::new(0);\n"
                "static HEX_TRACE_JOIN: std::sync::atomic::AtomicUsize = "
                "std::sync::atomic::AtomicUsize::new(0);\n"
                "static HEX_TRACE_RECOVERY: std::sync::atomic::AtomicUsize = "
                "std::sync::atomic::AtomicUsize::new(0);\n\n")
    body = replace_once(body, anchor, inserted + anchor +
                        "    HEX_SOLINAS_COUNT.fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n")
    module.write_text(body)

    tree = target / "hex_tree.rs"
    body = tree.read_text()
    body = replace_once(body,
        '    if count == 0 { return ("identity".to_owned(), 0, 0); }',
        '    let trace_start = HEX_SOLINAS_COUNT.load(std::sync::atomic::Ordering::Relaxed);\n'
        '    if count == 0 {\n'
        '        HEX_TRACE_JOIN.store(0, std::sync::atomic::Ordering::Relaxed);\n'
        '        HEX_TRACE_RECOVERY.store(0, std::sync::atomic::Ordering::Relaxed);\n'
        '        return ("identity".to_owned(), 0, 0);\n'
        '    }')
    body = replace_once(body,
        '    (point.affine_hex_binary_inverse(), rotations, last.product_depth)',
        '    let trace_join_end = HEX_SOLINAS_COUNT.load(std::sync::atomic::Ordering::Relaxed);\n'
        '    HEX_TRACE_JOIN.store(trace_join_end - trace_start, std::sync::atomic::Ordering::Relaxed);\n'
        '    let affine = point.affine_hex_binary_inverse();\n'
        '    let trace_end = HEX_SOLINAS_COUNT.load(std::sync::atomic::Ordering::Relaxed);\n'
        '    HEX_TRACE_RECOVERY.store(trace_end - trace_join_end, std::sync::atomic::Ordering::Relaxed);\n'
        '    (affine, rotations, last.product_depth)')
    body += ('\n// Instrumentation scope: one fixture case in a single-threaded CLI.\n'
             'pub(super) fn hex_trace_reset() {\n'
             '    HEX_SOLINAS_COUNT.store(0, std::sync::atomic::Ordering::Relaxed);\n'
             '    HEX_TRACE_JOIN.store(0, std::sync::atomic::Ordering::Relaxed);\n'
             '    HEX_TRACE_RECOVERY.store(0, std::sync::atomic::Ordering::Relaxed);\n'
             '}\n'
             'pub(super) fn hex_trace_read() -> (usize, usize, usize) {\n'
             '    (HEX_SOLINAS_COUNT.load(std::sync::atomic::Ordering::Relaxed),\n'
             '     HEX_TRACE_JOIN.load(std::sync::atomic::Ordering::Relaxed),\n'
             '     HEX_TRACE_RECOVERY.load(std::sync::atomic::Ordering::Relaxed))\n'
             '}\n')
    tree.write_text(body)

    cli = target / "hex_terminal_cli.rs"
    body = cli.read_text()
    body = replace_once(body,
        '        let start = Instant::now();\n        let (point, _, additions, retained_bytes, _, _, rotations) =',
        '        unit_orbit_windows::hex_trace_reset();\n'
        '        let start = Instant::now();\n        let (point, _, additions, retained_bytes, _, _, rotations) =')
    body = replace_once(body,
        '        assert_eq!(point, expected, "hex-terminal point mismatch at case {index}");',
        '        let (solinas_total, solinas_join, solinas_recovery) =\n'
        '            unit_orbit_windows::hex_trace_read();\n'
        '        assert_eq!(point, expected, "hex-terminal point mismatch at case {index}");')
    body = replace_once(body,
        '                      additions={additions} rotations={rotations} \\\n',
        '                      additions={additions} rotations={rotations} \\\n'
        '                      solinas_total={solinas_total} solinas_join={solinas_join} \\\n'
        '                      solinas_recovery={solinas_recovery} \\\n')
    body = replace_once(body,
        '                "rotations": rotations, "retained_bytes": retained_bytes}));',
        '                "rotations": rotations, "retained_bytes": retained_bytes,\n'
        '                "solinas_total": solinas_total, "solinas_join": solinas_join,\n'
        '                "solinas_recovery": solinas_recovery}));')
    cli.write_text(body)
    record.update({"schema": 8,
                   "instrument_source_sha256": digest(Path(__file__)),
                   "instrumented_module_sha256": digest(module),
                   "instrumented_tree_sha256": digest(tree),
                   "instrumented_cli_sha256": digest(cli)})
    (target / "overlay.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    prepare(args.target)
    if args.build:
        subprocess.run(["cargo", "build", "--offline", "--locked", "--release",
                        "--bin", "eisenstein_fixed"],
                       cwd=args.target / "experiments/prime-j0-secp256k1-native", check=True)
