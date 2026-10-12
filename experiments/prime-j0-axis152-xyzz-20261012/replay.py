#!/usr/bin/env python3
"""Compare axis-152 Jacobian and XYZZ outputs on independent public points."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-axis152-20261012"
MODULE = Path("experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs")
FIXTURES = (PARENT / "holdout2.json", HERE / "holdout.json")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def panel(binary: Path, fixture: Path) -> tuple[list[dict], bytes]:
    raw = subprocess.run([str(binary), "--axis152-panel", str(fixture)],
                         check=True, capture_output=True, text=True).stdout.encode()
    rows = [json.loads(line) for line in raw.splitlines()]
    return rows, raw


def run(reference: Path, candidate: Path, reference_record: Path,
        candidate_record: Path, development: bool) -> tuple[dict, dict]:
    ref = json.loads(reference_record.read_text())
    cand = json.loads(candidate_record.read_text())
    ref_module = reference_record.parent / MODULE
    cand_module = candidate_record.parent / MODULE
    cand_source = candidate_record.parent / "axis152_xyzz.rs"
    assert ref["compiled_module_sha256"] == digest(ref_module)
    assert cand["compiled_module_sha256"] == digest(cand_module)
    assert cand["reference_compiled_module_sha256"] == ref["compiled_module_sha256"]
    assert cand["candidate_transform_sha256"] == digest(HERE / "native_overlay_xyzz.py")
    assert cand["transformed_overlay_source_sha256"] == digest(cand_source)
    assert ref["base_module_sha256"] == cand["base_module_sha256"]
    assert ref["base_cli_sha256"] == cand["base_cli_sha256"]
    assert ref["overlay_module_sha256"] == cand["overlay_module_sha256"]
    assert ref["overlay_cli_sha256"] == cand["overlay_cli_sha256"]
    assert "let mut result = U256Jacobian::identity();" in (PARENT / "axis152_overlay.rs").read_text()
    assert "let mut result = U256XYZZ::identity();" in cand_source.read_text()
    fixtures = FIXTURES[:1] if development else FIXTURES
    panels = []
    for fixture in fixtures:
        expected = json.loads(fixture.read_text())
        left, left_raw = panel(reference, fixture)
        right, right_raw = panel(candidate, fixture)
        cases = expected["cases"]
        assert len(left) == len(right) == len(cases) == 512
        assert left == right
        points = []
        for index, (row, case) in enumerate(zip(right, cases, strict=True)):
            expected_point = ("identity" if case["expected_identity"] else
                              f"{case['expected_x_hex']}:{case['expected_y_hex']}")
            assert row["index"] == case["index"] == index
            assert row["verified"] is True and row["point"] == expected_point
            assert row["additions"] >= 0 and 0 <= row["rotations"] <= 2
            points.append(row["point"])
        panels.append({
            "fixture": str(fixture.relative_to(HERE.parent)),
            "fixture_sha256": digest(fixture),
            "cases": len(cases),
            "point_stream_sha256": sha256("\n".join(points).encode()).hexdigest(),
            "reference_stdout_sha256": sha256(left_raw).hexdigest(),
            "candidate_stdout_sha256": sha256(right_raw).hexdigest(),
            "total_additions": sum(row["additions"] for row in right),
            "total_rotations": sum(row["rotations"] for row in right),
            "retained_bytes": right[0]["retained_bytes"],
        })
    semantic = {
        "schema": 1, "status": "native_xyzz_matches_jacobian_and_independent_points",
        "panels": panels,
        "reference_compiled_module_sha256": digest(ref_module),
        "candidate_compiled_module_sha256": digest(cand_module),
        "source_sha256": digest(Path(__file__)),
        "transform_sha256": digest(HERE / "native_overlay_xyzz.py"),
    }
    local = {"platform": platform.platform(), "architecture": platform.machine(),
             "rustc": subprocess.run(["rustc", "--version"], check=True,
                                     capture_output=True, text=True).stdout.strip(),
             "reference_binary_sha256": digest(reference),
             "candidate_binary_sha256": digest(candidate),
             "reference_overlay_record_sha256": digest(reference_record),
             "candidate_overlay_record_sha256": digest(candidate_record)}
    return semantic, local


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--reference-record", type=Path, required=True)
    parser.add_argument("--candidate-record", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--development", action="store_true")
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    semantic, local = run(args.reference.resolve(), args.candidate.resolve(),
                          args.reference_record.resolve(), args.candidate_record.resolve(),
                          args.development)
    if args.development:
        print(json.dumps({"status": semantic["status"], "panels": semantic["panels"]},
                         sort_keys=True))
        return
    payload = (json.dumps(semantic, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        target = HERE / "replay.json"
        if target.exists():
            raise SystemExit("replay exists; use --check")
        target.write_bytes(payload)
        (HERE / "local-build.json").write_text(json.dumps(local, indent=2, sort_keys=True) + "\n")
    elif (HERE / "replay.json").read_bytes() != payload:
        raise SystemExit("XYZZ replay differs from frozen semantic receipt")
    print(json.dumps({"status": semantic["status"], "panels": len(semantic["panels"])},
                     sort_keys=True))


if __name__ == "__main__":
    main()
