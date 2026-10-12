#!/usr/bin/env python3
"""Build a disposable direct-terminal radix-256 evaluator from the frozen overlay."""

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
PARENT = EXP / "prime-j0-axis286-20261012"
sys.path.insert(0, str(PARENT))
import native_overlay_axis286 as parent_overlay  # noqa: E402

MODULE = parent_overlay.MODULE
CLI = parent_overlay.CLI


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def once(body: str, old: str, new: str) -> str:
    if body.count(old) != 1:
        raise RuntimeError(f"expected one direct-terminal transformation anchor: {old[:90]}")
    return body.replace(old, new, 1)


def prepare(target: Path) -> dict:
    target = target.resolve()
    record = parent_overlay.prepare(target)
    source = target / "direct_terminal.rs"
    cli_source = target / "direct_terminal_cli.rs"
    shutil.copyfile(HERE / source.name, source)
    shutil.copyfile(HERE / cli_source.name, cli_source)

    module = target / MODULE
    module.write_text(once(module.read_text(),
                           f'include!(r"{target / "axis286.rs"}");',
                           f'include!(r"{source}");'))

    cli = target / CLI
    body = once(cli.read_text(), f'include!(r"{target / "axis286_cli.rs"}");',
                f'include!(r"{cli_source}");')
    body = body.replace("--axis286-", "--direct-terminal-")
    body = body.replace("axis286_", "direct_terminal_")
    if "axis286" in body:
        raise RuntimeError("old CLI radix identifier remains")
    cli.write_text(body)

    record["schema"] = 5
    record["axis286_source_sha256"] = record["transformed_overlay_source_sha256"]
    record["transformed_overlay_source_sha256"] = digest(source)
    record["direct_terminal_cli_source_sha256"] = digest(cli_source)
    record["direct_terminal_transform_sha256"] = digest(Path(__file__))
    record["compiled_module_sha256"] = digest(module)
    record["compiled_cli_sha256"] = digest(cli)
    (target / "overlay.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "direct_terminal_overlay_prepared",
                      "source_sha256": record["transformed_overlay_source_sha256"]},
                     sort_keys=True))
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
