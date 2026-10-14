#!/usr/bin/env python3
"""Build a canonical Karatsuba Solinas copy of the axis-152 XYZZ evaluator."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-axis152-xyzz-20261012"
sys.path.insert(0, str(PARENT))
import native_overlay_xyzz as parent_overlay  # noqa: E402

MODULE = Path("experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs")
REPLACEMENTS = (
    (
        "    let x = super::hybrid_pair_mont(point.x);\n"
        "    let y = super::hybrid_pair_mont(point.y);\n"
        "    U256Affine { x, y }",
        "    let x = super::hybrid_pair_mont(point.x);\n"
        "    let y = super::hybrid_pair_mont(point.y);\n"
        "    let ctx = &super::HYBRID_FIELD.0;\n"
        "    U256Affine { x: ctx.from_montgomery(&x),\n"
        "                 y: ctx.from_montgomery(&y) }",
    ),
    ("build_u256_window_encoded(&atlas.digits, base, false)",
     "build_u256_window_encoded(&atlas.digits, base, true)"),
    ("let mut result = U256XYZZ::identity();",
     "let mut result = U256XYZZCanonical::<true>::identity();"),
    ("result = result.rotate_power_solinas(delta);",
     "result = result.rotate_power(delta);"),
    ("result = result.rotate_power_solinas(power);",
     "result = result.rotate_power(power);"),
    ("result = result.add_mixed(point.unit(code & 1));",
     "result = result.add_mixed(point.unit_solinas(code & 1));"),
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def prepare(target: Path) -> dict:
    target = target.resolve()
    record = parent_overlay.prepare(target)
    original = target / "axis152_xyzz.rs"
    source = original.read_text()
    for old, new in REPLACEMENTS:
        if source.count(old) != 1:
            raise RuntimeError(f"expected one canonical transformation anchor: {old[:90]}")
        source = source.replace(old, new, 1)
    transformed = target / "axis152_solinas.rs"
    transformed.write_text(source)
    module = target / MODULE
    module_body = module.read_text()
    old_include = f'include!(r"{original}");'
    new_include = f'include!(r"{transformed}");'
    if module_body.count(old_include) != 1:
        raise RuntimeError("XYZZ overlay include anchor changed")
    module.write_text(module_body.replace(old_include, new_include, 1))
    record["schema"] = 3
    record["solinas_transform_sha256"] = digest(Path(__file__))
    record["xyzz_compiled_module_sha256"] = record["compiled_module_sha256"]
    record["xyzz_overlay_source_sha256"] = record["transformed_overlay_source_sha256"]
    record["compiled_module_sha256"] = digest(module)
    record["transformed_overlay_source_sha256"] = digest(transformed)
    record["replacements"] = [{"old": old, "new": new} for old, new in REPLACEMENTS]
    (target / "overlay.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "axis152_solinas_overlay_prepared",
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
