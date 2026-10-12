#!/usr/bin/env python3
"""Build an axis-152 copy with an XYZZ accumulator from pinned source."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-axis152-20261012"
sys.path.insert(0, str(PARENT))
import native_overlay as parent_overlay  # noqa: E402

MODULE = Path("experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs")
START = "fn axis152_evaluate(selected: &[(U256Affine, usize)]) -> (String, usize) {"
END = "pub(super) fn multiply_u256_axis152("
REPLACEMENTS = (
    ("let mut result = U256Jacobian::identity();", "let mut result = U256XYZZ::identity();"),
    ("result = result.rotate_power(delta);", "result = result.rotate_power_solinas(delta);"),
    ("result = result.rotate_power(power);", "result = result.rotate_power_solinas(power);"),
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def prepare(target: Path) -> dict:
    target = target.resolve()
    record = parent_overlay.prepare(target)
    module = target / MODULE
    source = (PARENT / "axis152_overlay.rs").read_text()
    if source.count(START) != 1 or source.count(END) != 1:
        raise RuntimeError("axis-152 evaluator anchors changed")
    begin = source.index(START)
    finish = source.index(END, begin)
    body = source[begin:finish]
    for old, new in REPLACEMENTS:
        if body.count(old) != 1:
            raise RuntimeError(f"expected one evaluator anchor: {old}")
        body = body.replace(old, new, 1)
    transformed = target / "axis152_xyzz.rs"
    transformed.write_text(source[:begin] + body + source[finish:])
    module_body = module.read_text()
    old_include = f'include!(r"{PARENT / "axis152_overlay.rs"}");'
    new_include = f'include!(r"{transformed}");'
    if module_body.count(old_include) != 1:
        raise RuntimeError("parent overlay include anchor changed")
    module.write_text(module_body.replace(old_include, new_include, 1))
    record["schema"] = 2
    record["candidate_transform_sha256"] = digest(Path(__file__))
    record["reference_compiled_module_sha256"] = record["compiled_module_sha256"]
    record["compiled_module_sha256"] = digest(module)
    record["transformed_overlay_source_sha256"] = digest(transformed)
    record["replacements"] = [{"old": old, "new": new} for old, new in REPLACEMENTS]
    (target / "overlay.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "axis152_xyzz_overlay_prepared",
                      "reference_module": record["reference_compiled_module_sha256"],
                      "candidate_module": record["compiled_module_sha256"]}, sort_keys=True))
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
