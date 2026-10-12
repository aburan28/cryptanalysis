#!/usr/bin/env python3
"""Check the native overlay against all frozen independent public points."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import platform
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = ROOT / "experiments/prime-j0-secp256k1-native"
MODULE = NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
CLI = NATIVE / "src/bin/eisenstein_fixed.rs"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def fields(line: str) -> dict[str, str]:
    return dict(word.split("=", 1) for word in line.split() if "=" in word)


def run(binary: Path, overlay_record: Path) -> tuple[dict, bytes, dict]:
    record = json.loads(overlay_record.read_text())
    sources = {
        "base_module_sha256": digest(MODULE),
        "base_cli_sha256": digest(CLI),
        "base_native_cargo_sha256": digest(NATIVE / "Cargo.toml"),
        "base_native_lock_sha256": digest(NATIVE / "Cargo.lock"),
        "overlay_module_sha256": digest(HERE / "radix569_overlay.rs"),
        "overlay_cli_sha256": digest(HERE / "radix569_cli.rs"),
        "overlay_builder_sha256": digest(HERE / "native_overlay.py"),
    }
    assert all(record[key] == value for key, value in sources.items())
    copied_native = overlay_record.parent / "experiments/prime-j0-secp256k1-native"
    assert record["compiled_module_sha256"] == digest(
        copied_native / "src/bin/eisenstein_fixed/unit_orbit_windows.rs")
    assert record["compiled_cli_sha256"] == digest(
        copied_native / "src/bin/eisenstein_fixed.rs")
    audit_raw = subprocess.run([str(binary), "--radix569-audit"],
                               check=True, capture_output=True, text=True).stdout.strip()
    audit = fields(audit_raw)
    assert audit["verified"] == "1"
    assert int(audit["top_states"]) == 327_235
    assert int(audit["top_orbits"]) == 54_540
    assert int(audit["point_entries"]) == 756_033
    retained = int(audit["retained_bytes"])
    assert 48_386_112 <= retained < 140 * (1 << 20)
    atlas_bytes = subprocess.run([str(binary), "--radix569-atlas-bytes"],
                                 check=True, capture_output=True).stdout
    split = 53_961 * 4
    assert len(atlas_bytes) == split + 54_539 * 4
    ordinary_digest = sha256(atlas_bytes[:split]).hexdigest()
    top_digest = sha256(atlas_bytes[split:]).hexdigest()
    assert ordinary_digest == json.loads((HERE / "design.json").read_text())["canonical_digits_sha256"]
    assert top_digest == json.loads((HERE / "topball.json").read_text())["canonical_top_pairs_sha256"]
    raw = subprocess.run([str(binary), "--radix569-panel", str(HERE / "holdout.json")],
                         check=True, capture_output=True, text=True).stdout
    native_rows = [json.loads(line) for line in raw.splitlines()]
    frozen_rows = [json.loads(line) for line in (HERE / "holdout-rows.jsonl").read_text().splitlines()]
    fixture = json.loads((HERE / "holdout.json").read_text())
    assert len(native_rows) == len(frozen_rows) == len(fixture["cases"]) == 512
    rows = []
    for index, (native, frozen, case) in enumerate(zip(native_rows, frozen_rows, fixture["cases"], strict=True)):
        assert native["index"] == frozen["index"] == case["index"] == index
        assert native["verified"] is True
        assert native["point"] == frozen["point"]
        assert native["rotations"] == frozen["candidate"]["rotations"]
        assert native["additions"] + 1 == frozen["candidate"]["terms"]
        assert native["retained_bytes"] == retained
        rows.append({key: native[key] for key in ("index", "verified", "point", "additions", "rotations")})
    points = "\n".join(row["point"] for row in rows)
    expected = json.loads((HERE / "holdout-replay.json").read_text())
    assert sha256(points.encode()).hexdigest() == expected["point_digest"]
    total_rotations = sum(row["rotations"] for row in rows)
    assert total_rotations == expected["totals"]["candidate_rotations"]
    total_additions = sum(row["additions"] for row in rows)
    assert total_additions == expected["totals"]["candidate_terms"] - len(rows)
    canonical_rows = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                                for row in rows) + "\n").encode()
    semantic = {
        "schema": 1,
        "status": "native_group_replay_verified",
        "cases": len(rows),
        "top_states_audited": int(audit["top_states"]),
        "top_orbits_audited": int(audit["top_orbits"]),
        "point_entries": int(audit["point_entries"]),
        "ordinary_atlas_sha256": ordinary_digest,
        "top_atlas_sha256": top_digest,
        "affine_point_bytes_at_64_each": 48_386_112,
        "total_additions": total_additions,
        "total_rotations": total_rotations,
        "point_digest": sha256(points.encode()).hexdigest(),
        "rows_sha256": sha256(canonical_rows).hexdigest(),
        "holdout_sha256": digest(HERE / "holdout.json"),
        "frozen_replay_sha256": digest(HERE / "holdout-replay.json"),
        "pareto_plan_sha256": digest(ROOT / "experiments/prime-j0-pareto-tree-20261012/plans.bin"),
        "sources": sources,
        "replay_source_sha256": digest(Path(__file__)),
    }
    local = {
        "schema": 1,
        "status": "local_native_build_and_replay",
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "rustc": subprocess.run(["rustc", "--version"], check=True, capture_output=True, text=True).stdout.strip(),
        "binary_sha256": digest(binary),
        "retained_bytes": retained,
        "overlay_record_sha256": digest(overlay_record),
        "semantic_receipt_sha256": sha256((json.dumps(semantic, indent=2, sort_keys=True) + "\n").encode()).hexdigest(),
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
        (HERE / "native-local-build.json").write_text(json.dumps(local, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": semantic["status"], "cases": semantic["cases"],
                          "retained_bytes": local["retained_bytes"]}, sort_keys=True))
    elif receipt_path.read_bytes() != payload or rows_path.read_bytes() != rows:
        raise SystemExit("native replay differs from frozen semantic receipt")
    else:
        print("native radix-569 top atlas and 512 point replays verified")


if __name__ == "__main__":
    main()
