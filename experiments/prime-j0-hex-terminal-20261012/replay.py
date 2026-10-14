#!/usr/bin/env python3
"""Compare the hex-terminal evaluator to radix-286 and independent points."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
MODULE = Path("experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs")
CLI = Path("experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs")
FIXTURES = (
    EXP / "prime-j0-axis286-20261012/holdout.json",
    EXP / "prime-j0-power2-direct-terminal-20261012/holdout.json",
    EXP / "prime-j0-power2-direct-terminal-20261012/holdout2.json",
    HERE / "holdout.json",
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def panel(binary: Path, flag: str, fixture: Path) -> tuple[list[dict], bytes]:
    output = subprocess.run([str(binary), flag, str(fixture)], check=True,
                            capture_output=True, text=True).stdout.encode()
    return [json.loads(line) for line in output.splitlines()], output


def run(reference: Path, candidate: Path, reference_record: Path,
        candidate_record: Path, development: bool) -> tuple[dict, dict]:
    ref = json.loads(reference_record.read_text())
    cand = json.loads(candidate_record.read_text())
    for path, record in ((reference_record, ref), (candidate_record, cand)):
        assert digest(path.parent / MODULE) == record["compiled_module_sha256"]
        assert digest(path.parent / CLI) == record["compiled_cli_sha256"]
    source = candidate_record.parent / "hex_terminal.rs"
    cli_source = candidate_record.parent / "hex_terminal_cli.rs"
    assert digest(source) == cand["transformed_overlay_source_sha256"]
    assert digest(cli_source) == cand["hex_terminal_cli_source_sha256"]
    assert digest(HERE / "native_overlay_hex.py") == cand["hex_terminal_transform_sha256"]
    for key in ("base_module_sha256", "base_cli_sha256", "overlay_module_sha256",
                "overlay_cli_sha256"):
        assert ref[key] == cand[key]
    assert ref["transformed_overlay_source_sha256"] == cand["axis286_source_sha256"]
    assert "const HEX_TERMINAL_WINDOWS: usize = 15;" in source.read_text()
    fixtures = FIXTURES[:1] if development else FIXTURES
    panels = []
    for fixture in fixtures:
        cases = json.loads(fixture.read_text())["cases"]
        left, left_raw = panel(reference, "--axis286-panel", fixture)
        right, right_raw = panel(candidate, "--hex-terminal-panel", fixture)
        assert len(cases) == len(left) == len(right) == 512
        points = []
        for index, (a, b, case) in enumerate(zip(left, right, cases, strict=True)):
            expected = ("identity" if case["expected_identity"] else
                        f"{case['expected_x_hex']}:{case['expected_y_hex']}")
            assert a["index"] == b["index"] == case["index"] == index
            assert a["point"] == b["point"] == expected
            assert a["verified"] is True and b["verified"] is True
            assert b["additions"] <= a["additions"]
            assert 0 <= a["rotations"] <= 2 and 0 <= b["rotations"] <= 2
            points.append(expected)
        panels.append({
            "fixture": str(fixture.relative_to(EXP)),
            "fixture_sha256": digest(fixture),
            "cases": len(cases),
            "point_stream_sha256": sha256("\n".join(points).encode()).hexdigest(),
            "reference_stdout_sha256": sha256(left_raw).hexdigest(),
            "candidate_stdout_sha256": sha256(right_raw).hexdigest(),
            "reference_additions": sum(row["additions"] for row in left),
            "candidate_additions": sum(row["additions"] for row in right),
            "reference_rotations": sum(row["rotations"] for row in left),
            "candidate_rotations": sum(row["rotations"] for row in right),
            "reference_retained_bytes": left[0]["retained_bytes"],
            "candidate_retained_bytes": right[0]["retained_bytes"],
        })
    semantic = {
        "schema": 1,
        "status": "hex_terminal_matches_axis286_and_independent_points",
        "panels": panels,
        "base_module_sha256": ref["base_module_sha256"],
        "axis286_source_sha256": ref["transformed_overlay_source_sha256"],
        "hex_terminal_source_sha256": cand["transformed_overlay_source_sha256"],
        "hex_terminal_cli_source_sha256": cand["hex_terminal_cli_source_sha256"],
        "source_sha256": digest(Path(__file__)),
        "transform_sha256": digest(HERE / "native_overlay_hex.py"),
    }
    local = {
        "platform": platform.platform(), "architecture": platform.machine(),
        "rustc": subprocess.run(["rustc", "--version"], check=True,
                                capture_output=True, text=True).stdout.strip(),
        "reference_binary_sha256": digest(reference),
        "candidate_binary_sha256": digest(candidate),
        "reference_compiled_module_sha256": digest(reference_record.parent / MODULE),
        "candidate_compiled_module_sha256": digest(candidate_record.parent / MODULE),
        "reference_compiled_cli_sha256": digest(reference_record.parent / CLI),
        "candidate_compiled_cli_sha256": digest(candidate_record.parent / CLI),
    }
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
        raise SystemExit("hex-terminal replay differs from frozen semantic receipt")
    print(json.dumps({"status": semantic["status"], "panels": len(semantic["panels"])},
                     sort_keys=True))


if __name__ == "__main__":
    main()
