#!/usr/bin/env python3
"""Build a disposable native crate with the axis-416 code included."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP = ROOT / "experiments"
NATIVE = EXP / "prime-j0-secp256k1-native"
MODULE = Path("src/bin/eisenstein_fixed/unit_orbit_windows.rs")
CLI = Path("src/bin/eisenstein_fixed.rs")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def once(body: str, old: str, new: str) -> str:
    if body.count(old) != 1:
        raise RuntimeError(f"overlay anchor count {body.count(old)} for {old[:90]!r}")
    return body.replace(old, new, 1)


def prepare(target: Path) -> dict:
    if target.exists():
        raise SystemExit(f"target exists: {target}")
    target.mkdir(parents=True)
    (target / "suite").symlink_to((ROOT / "suite").resolve(), target_is_directory=True)
    out_exp = target / "experiments"
    out_exp.mkdir()
    for child in EXP.iterdir():
        if child.name == NATIVE.name:
            continue
        (out_exp / child.name).symlink_to(child.resolve(), target_is_directory=child.is_dir())
    out_native = out_exp / NATIVE.name
    shutil.copytree(NATIVE, out_native, ignore=shutil.ignore_patterns("target", "__pycache__"))
    module_path = out_native / MODULE
    cli_path = out_native / CLI
    module_body = module_path.read_text()
    cli_body = cli_path.read_text()
    module_body += f'\ninclude!(r"{HERE / "axis416_overlay.rs"}");\n'
    cli_body = once(cli_body,
        "    let args: Vec<String> = std::env::args().skip(1).collect();\n",
        "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
        "    if args == [\"--axis416-audit\"] {\n"
        "        axis416_audit_cli();\n"
        "        return;\n"
        "    }\n"
        "    if args == [\"--axis416-atlas-bytes\"] {\n"
        "        axis416_atlas_cli();\n"
        "        return;\n"
        "    }\n"
        "    if args.len() == 2 && args[0] == \"--axis416-panel\" {\n"
        "        axis416_fixture(&args[1], None);\n"
        "        return;\n"
        "    }\n"
        "    if args.len() == 3 && args[0] == \"--axis416-case\" {\n"
        "        axis416_fixture(&args[1], Some(args[2].parse().expect(\"index\")));\n"
        "        return;\n"
        "    }\n")
    cli_body += f'\ninclude!(r"{HERE / "axis416_cli.rs"}");\n'
    module_path.write_text(module_body)
    cli_path.write_text(cli_body)
    record = {
        "schema": 1,
        "base_native_cargo_sha256": digest(NATIVE / "Cargo.toml"),
        "base_native_lock_sha256": digest(NATIVE / "Cargo.lock"),
        "base_module_sha256": digest(NATIVE / MODULE),
        "base_cli_sha256": digest(NATIVE / CLI),
        "overlay_module_sha256": digest(HERE / "axis416_overlay.rs"),
        "overlay_cli_sha256": digest(HERE / "axis416_cli.rs"),
        "overlay_builder_sha256": digest(Path(__file__)),
        "compiled_module_sha256": digest(module_path),
        "compiled_cli_sha256": digest(cli_path),
    }
    (target / "overlay.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, sort_keys=True))
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    prepare(args.target.resolve())
    if args.build:
        subprocess.run(["cargo", "build", "--offline", "--locked", "--release",
                        "--bin", "eisenstein_fixed"],
                       cwd=args.target / "experiments" / NATIVE.name, check=True)


if __name__ == "__main__":
    main()
