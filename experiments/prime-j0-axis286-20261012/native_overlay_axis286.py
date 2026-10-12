#!/usr/bin/env python3
"""Build a disposable fourteen-window radix-286 Solinas evaluator."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
PARENT = EXP / "prime-j0-axis152-solinas-20261012"
sys.path.insert(0, str(PARENT))
import native_overlay_solinas as parent_overlay  # noqa: E402

MODULE = Path("experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs")
CLI = Path("experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs")
REPLACEMENTS = (
    ("const AXIS152: usize = 152;", "const AXIS152: usize = 286;"),
    ("const AXIS152_WINDOWS: usize = 16;", "const AXIS152_WINDOWS: usize = 14;"),
    ("const AXIS152_TOP_CAP: i64 = 17_574_891;",
     "const AXIS152_TOP_CAP: i64 = 192_971_294;"),
    ("const AXIS152_U_MAX: usize = 4_840;",
     "const AXIS152_U_MAX: usize = 16_040;"),
    ("const AXIS152_B_MAX: usize = 3_226;",
     "const AXIS152_B_MAX: usize = 10_693;"),
    ("assert_eq!(atlas.digits.len(), 3_852);",
     "assert_eq!(atlas.digits.len(), 13_634);"),
    ("assert_eq!(entries, 69_698);", "assert_eq!(entries, 217_609);"),
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def once(body: str, old: str, new: str) -> str:
    if body.count(old) != 1:
        raise RuntimeError(f"expected one radix-286 transformation anchor: {old[:90]}")
    return body.replace(old, new, 1)


def prepare(target: Path) -> dict:
    target = target.resolve()
    record = parent_overlay.prepare(target)
    old_source = target / "axis152_solinas.rs"
    source = old_source.read_text()
    for old, new in REPLACEMENTS:
        source = once(source, old, new)
    source = source.replace("AXIS152", "AXIS286").replace("axis152", "axis286")
    source = source.replace("axis-152", "axis-286")
    if "AXIS152" in source or "axis152" in source:
        raise RuntimeError("old radix identifier remains")
    new_source = target / "axis286.rs"
    new_source.write_text(source)

    module = target / MODULE
    module.write_text(once(module.read_text(),
                           f'include!(r"{old_source}");',
                           f'include!(r"{new_source}");'))

    old_cli_source = EXP / "prime-j0-axis152-20261012/axis152_cli.rs"
    new_cli_source = target / "axis286_cli.rs"
    cli_source = old_cli_source.read_text().replace("axis152", "axis286")
    cli_source = cli_source.replace("axis-152", "axis-286")
    cli_source = once(cli_source, "point_entries=69698", "point_entries=217609")
    new_cli_source.write_text(cli_source)
    cli = target / CLI
    cli_body = cli.read_text()
    cli_body = once(cli_body, f'include!(r"{old_cli_source}");',
                    f'include!(r"{new_cli_source}");')
    cli_body = cli_body.replace("--axis152-", "--axis286-")
    cli_body = cli_body.replace("axis152_", "axis286_")
    if "axis152" in cli_body:
        raise RuntimeError("old CLI radix identifier remains")
    cli.write_text(cli_body)

    record["schema"] = 4
    record["axis286_transform_sha256"] = digest(Path(__file__))
    record["axis152_solinas_source_sha256"] = record["transformed_overlay_source_sha256"]
    record["transformed_overlay_source_sha256"] = digest(new_source)
    record["axis286_cli_source_sha256"] = digest(new_cli_source)
    record["compiled_module_sha256"] = digest(module)
    record["compiled_cli_sha256"] = digest(cli)
    record["replacements"] = [{"old": old, "new": new} for old, new in REPLACEMENTS]
    (target / "overlay.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "axis286_overlay_prepared",
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
