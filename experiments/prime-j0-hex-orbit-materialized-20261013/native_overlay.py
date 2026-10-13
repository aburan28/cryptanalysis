#!/usr/bin/env python3
"""Build an absolute-gauge hex tree with a compressed three-image x table."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-hex-dag-pareto-20261013"
sys.path.insert(0, str(PRIOR))
import native_overlay_pareto as parent  # noqa: E402


def replace_once(body: str, old: str, new: str) -> str:
    assert body.count(old) == 1, old[:100]
    return body.replace(old, new, 1)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def prepare(target: Path) -> dict:
    target = target.resolve()
    record = parent.prepare(target)
    shutil.copyfile(HERE / "plans.bin", target / "plans.bin")

    source = target / "hex_terminal.rs"
    body = source.read_text()
    body = replace_once(body, "struct HexTerminalTables {",
        "fn hex_materialize(point: U256Affine) -> U256TwoXAffine {\n"
        "    let x_beta = u256_mul_solinas_with::<true>(point.x, U256_BETA_CANONICAL[1]);\n"
        "    U256TwoXAffine { x: point.x, minus_x_beta2: u256_add(point.x, x_beta), y: point.y }\n"
        "}\n\nstruct HexTerminalTables {")
    body = replace_once(body, "ordinary: Vec<Box<[U256Affine]>>", "ordinary: Vec<Box<[U256TwoXAffine]>>")
    body = replace_once(body, "top: Box<[U256Affine]>", "top: Box<[U256TwoXAffine]>")
    body = replace_once(body, "assert_eq!(size_of::<U256Affine>(), 64);",
                        "assert_eq!(size_of::<U256TwoXAffine>(), 96);")
    body = replace_once(body,
        "ordinary.push(build_u256_window_encoded(&atlas.digits, base, true));",
        "ordinary.push(build_u256_window_encoded(&atlas.digits, base, true)\n"
        "    .iter().copied().map(hex_materialize).collect::<Vec<_>>().into_boxed_slice());")
    body = replace_once(body,
        "top_points.push(U256Affine { x: super::U256::ZERO, y: super::U256::ZERO });",
        "top_points.push(hex_materialize(U256Affine { x: super::U256::ZERO, y: super::U256::ZERO }));")
    body = replace_once(body,
        "top_points.extend(batch_to_affine(&top_projective).into_iter().map(hex_terminal_encode));",
        "top_points.extend(batch_to_affine(&top_projective).into_iter()\n"
        "    .map(hex_terminal_encode).map(hex_materialize));")
    body = replace_once(body, "entries * size_of::<U256Affine>()",
                        "entries * size_of::<U256TwoXAffine>()")
    body = replace_once(body,
        "fn hex_terminal_evaluate(selected: &[(U256Affine, usize)])",
        "fn hex_terminal_evaluate(selected: &[(U256TwoXAffine, usize)])")
    body = replace_once(body, "point.unit_solinas(code & 1)", "point.unit(code & 1)")
    source.write_text(body)

    tree = target / "hex_tree.rs"
    body = tree.read_text()
    body = replace_once(body,
        "selected: &[(U256Affine, usize)]", "selected: &[(U256TwoXAffine, usize)]")
    body = replace_once(body,
        "point: GaugeTreePoint::Affine(point.unit_solinas(code & 1)),\n            gauge,",
        "point: GaugeTreePoint::Affine(point.unit(code)),\n            gauge: 0,")
    tree.write_text(body)

    record.update({"schema": 10, "hex_tree_plan_sha256": digest(target / "plans.bin"),
                   "absolute_gauge_plan_sha256": digest(target / "plans.bin"),
                   "absolute_gauge_plan_receipt_sha256": digest(HERE / "plans.json"),
                   "materialized_table_sha256": digest(source),
                   "materialized_tree_sha256": digest(tree),
                   "materialized_overlay_sha256": digest(Path(__file__))})
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
