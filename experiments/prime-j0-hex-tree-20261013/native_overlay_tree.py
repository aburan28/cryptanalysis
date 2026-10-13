#!/usr/bin/env python3
"""Build a disposable hex-terminal evaluator with the gauge-tree schedule."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
PARENT = EXP / "prime-j0-hex-terminal-20261012"
sys.path.insert(0, str(PARENT))
import native_overlay_hex as parent_overlay  # noqa: E402


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def once(body: str, old: str, new: str) -> str:
    if body.count(old) != 1:
        raise RuntimeError(f"expected one tree-overlay anchor: {old[:90]}")
    return body.replace(old, new, 1)


def prepare(target: Path) -> dict:
    target = target.resolve()
    record = parent_overlay.prepare(target)
    source = target / "hex_tree.rs"
    plans = target / "plans.bin"
    shutil.copyfile(HERE / source.name, source)
    shutil.copyfile(HERE / plans.name, plans)
    module = target / parent_overlay.MODULE
    old = f'include!(r"{target / "hex_terminal.rs"}");'
    module.write_text(once(module.read_text(), old,
                           old + f'\ninclude!(r"{source}");'))
    helper = target / "hex_terminal_cli.rs"
    body = once(helper.read_text(),
                        'unit_orbit_windows::multiply_u256_hex_terminal(words)',
                        'unit_orbit_windows::multiply_u256_hex_tree(words)')
    old_retained = 'let retained = unit_orbit_windows::hex_terminal_warm();'
    if body.count(old_retained) != 2:
        raise RuntimeError("hex-terminal retained-byte anchors changed")
    helper.write_text(body.replace(
        old_retained,
        'let retained = unit_orbit_windows::hex_terminal_warm() + 46512;'))
    cli = target / parent_overlay.CLI
    record.update({
        "schema": 6,
        "hex_tree_source_sha256": digest(source),
        "hex_tree_plan_sha256": digest(plans),
        "hex_tree_cli_source_sha256": digest(helper),
        "hex_tree_transform_sha256": digest(Path(__file__)),
        "compiled_module_sha256": digest(module),
        "compiled_cli_sha256": digest(cli),
    })
    (target / "overlay.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "hex_tree_overlay_prepared",
                      "source_sha256": record["hex_tree_source_sha256"]}, sort_keys=True))
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    prepare(args.target)
    if args.build:
        subprocess.run(["cargo", "build", "--offline", "--locked", "--release",
                        "--bin", "eisenstein_fixed"],
                       cwd=args.target / "experiments/prime-j0-secp256k1-native", check=True)


if __name__ == "__main__":
    main()
