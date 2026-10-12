#!/usr/bin/env python3
"""Bind the native split-top tables and point outputs to the frozen holdout."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import platform
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP = ROOT / "experiments"
FORMAT = EXP / "prime-j0-split-top-20261012"
NATIVE = EXP / "prime-j0-secp256k1-native"
MODULE = NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
CLI = NATIVE / "src/bin/eisenstein_fixed.rs"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def fields(line: str) -> dict[str, str]:
    return dict(word.split("=", 1) for word in line.split() if "=" in word)


def rectangle_digest(a_lo: int, a_hi: int, b_lo: int, b_hi: int) -> str:
    value = sha256(struct.pack("<hh", 0, 0))
    for a in range(a_lo, a_hi + 1):
        for b in range(b_lo, b_hi + 1):
            if a or b:
                value.update(struct.pack("<hh", a, b))
    return value.hexdigest()


def run(binary: Path, overlay_record: Path) -> tuple[dict, bytes, dict]:
    record = json.loads(overlay_record.read_text())
    sources = {
        "base_module_sha256": digest(MODULE),
        "base_cli_sha256": digest(CLI),
        "base_native_cargo_sha256": digest(NATIVE / "Cargo.toml"),
        "base_native_lock_sha256": digest(NATIVE / "Cargo.lock"),
        "overlay_module_sha256": digest(HERE / "split671_overlay.rs"),
        "overlay_cli_sha256": digest(HERE / "split671_cli.rs"),
        "overlay_builder_sha256": digest(HERE / "native_overlay.py"),
    }
    assert all(record[key] == value for key, value in sources.items())
    copied_native = overlay_record.parent / "experiments/prime-j0-secp256k1-native"
    assert record["compiled_module_sha256"] == digest(
        copied_native / "src/bin/eisenstein_fixed/unit_orbit_windows.rs")
    assert record["compiled_cli_sha256"] == digest(
        copied_native / "src/bin/eisenstein_fixed.rs")
    audit = fields(subprocess.run([str(binary), "--split671-audit"],
                                  check=True, capture_output=True, text=True).stdout.strip())
    assert audit["verified"] == "1"
    assert int(audit["residues"]) == 450_241
    assert int(audit["point_entries"]) == 1_044_625
    retained = int(audit["retained_bytes"])
    assert 66_856_000 <= retained < 140 * (1 << 20)
    atlas_bytes = subprocess.run([str(binary), "--split671-atlas-bytes"],
                                 check=True, capture_output=True).stdout
    cut1 = 75_041 * 4
    cut2 = (75_041 + 65_536) * 4
    assert len(atlas_bytes) == (75_041 + 65_536 + 78_597) * 4
    ordinary_digest = sha256(atlas_bytes[:cut1]).hexdigest()
    low_digest = sha256(atlas_bytes[cut1:cut2]).hexdigest()
    high_digest = sha256(atlas_bytes[cut2:]).hexdigest()
    assert ordinary_digest == json.loads((FORMAT / "design.json").read_text())["ordinary_atlas_sha256"]
    assert low_digest == rectangle_digest(-128, 127, -128, 127)
    assert high_digest == rectangle_digest(-184, 184, -106, 106)
    raw = subprocess.run([str(binary), "--split671-panel", str(FORMAT / "holdout.json")],
                         check=True, capture_output=True, text=True).stdout
    native_rows = [json.loads(line) for line in raw.splitlines()]
    frozen_rows = [json.loads(line) for line in (FORMAT / "holdout-rows.jsonl").read_text().splitlines()]
    fixture = json.loads((FORMAT / "holdout.json").read_text())
    assert len(native_rows) == len(frozen_rows) == len(fixture["cases"]) == 512
    rows = []
    for index, (native, frozen, case) in enumerate(
            zip(native_rows, frozen_rows, fixture["cases"], strict=True)):
        assert native["index"] == frozen["index"] == case["index"] == index
        assert native["verified"] is True
        assert native["point"] == frozen["point"]
        assert native["rotations"] == frozen["cost"]["rotations"]
        assert native["additions"] + 1 == frozen["cost"]["terms"]
        assert native["retained_bytes"] == retained
        rows.append({key: native[key] for key in
                     ("index", "verified", "point", "additions", "rotations")})
    point_bytes = ("\n".join(row["point"] for row in rows) + "\n").encode()
    expected = json.loads((FORMAT / "holdout-replay.json").read_text())
    assert sha256(point_bytes).hexdigest() == expected["point_stream_sha256"]
    total_rotations = sum(row["rotations"] for row in rows)
    total_additions = sum(row["additions"] for row in rows)
    assert total_rotations == expected["totals"]["split_rotations"] == 1_195
    assert total_additions == 6_656
    canonical_rows = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                                for row in rows) + "\n").encode()
    semantic = {
        "schema": 1, "status": "native_split_group_replay_verified",
        "cases": len(rows), "residues_audited": int(audit["residues"]),
        "point_entries": int(audit["point_entries"]),
        "ordinary_atlas_sha256": ordinary_digest,
        "low_atlas_sha256": low_digest,
        "high_atlas_sha256": high_digest,
        "affine_point_bytes_at_64_each": 66_856_000,
        "total_additions": total_additions,
        "total_rotations": total_rotations,
        "point_stream_sha256": sha256(point_bytes).hexdigest(),
        "rows_sha256": sha256(canonical_rows).hexdigest(),
        "holdout_sha256": digest(FORMAT / "holdout.json"),
        "frozen_replay_sha256": digest(FORMAT / "holdout-replay.json"),
        "pareto_plan_sha256": digest(EXP / "prime-j0-pareto-tree-20261012/plans.bin"),
        "sources": sources,
        "replay_source_sha256": digest(Path(__file__)),
    }
    local = {
        "schema": 1, "status": "local_native_build_and_replay",
        "platform": platform.platform(), "architecture": platform.machine(),
        "rustc": subprocess.run(["rustc", "--version"], check=True,
                                capture_output=True, text=True).stdout.strip(),
        "binary_sha256": digest(binary),
        "retained_bytes": retained,
        "overlay_record_sha256": digest(overlay_record),
        "semantic_receipt_sha256": sha256((json.dumps(semantic, indent=2, sort_keys=True)
                                           + "\n").encode()).hexdigest(),
    }
    return semantic, canonical_rows, local


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--overlay-record", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    semantic, rows, local = run(args.binary.resolve(), args.overlay_record.resolve())
    payload = (json.dumps(semantic, indent=2, sort_keys=True) + "\n").encode()
    receipt_path = HERE / "native-replay.json"
    rows_path = HERE / "native-rows.jsonl"
    if args.write:
        if receipt_path.exists() or rows_path.exists():
            raise SystemExit("native replay exists; use --check")
        receipt_path.write_bytes(payload)
        rows_path.write_bytes(rows)
        (HERE / "native-local-build.json").write_text(
            json.dumps(local, indent=2, sort_keys=True) + "\n")
    elif receipt_path.read_bytes() != payload or rows_path.read_bytes() != rows:
        raise SystemExit("native replay differs from frozen semantic receipt")
    print(json.dumps({"status": semantic["status"], "cases": semantic["cases"],
                      "retained_bytes": local["retained_bytes"]}, sort_keys=True))


if __name__ == "__main__":
    main()
