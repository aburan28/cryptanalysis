#!/usr/bin/env python3
"""Replay the hash-pinned n53 L384 archive from a local crypto Git checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

from accelerated_audit import audit_panel

HERE = Path(__file__).resolve().parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def blob(repo: Path, commit: str, path: str) -> bytes:
    return git(repo, "show", f"{commit}:{path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crypto-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = args.crypto_repo.resolve()
    source = json.loads((HERE / "source.json").read_text())
    assert source["schema"] == "n53-l384-archive-bridge-v1"
    archive_commit = source["archive_commit"]
    release_commit = source["release_commit"]
    archive_dir = source["archive_dir"]
    assert len(archive_commit) == len(release_commit) == 40
    assert git(repo, "cat-file", "-t", archive_commit).strip() == b"commit"
    assert git(repo, "cat-file", "-t", release_commit).strip() == b"commit"

    with tempfile.TemporaryDirectory(prefix="n53-l384-replay-") as name:
        root = Path(name)
        paths = git(repo, "ls-tree", "-r", "--name-only", archive_commit,
                    "--", archive_dir).decode().splitlines()
        assert paths and all(path.startswith(archive_dir + "/") for path in paths)
        for path in paths:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob(repo, archive_commit, path))
        experiment = root / archive_dir
        freeze = json.loads((experiment / "FROZEN.json").read_text())
        assert freeze["schema"] == "n53_l384_certified_coldbase_freeze_v1"
        sys.path.insert(0, str(experiment))
        import check_protocol  # type: ignore[import-not-found]

        release_keys = set(source["release_source_keys"])
        assert release_keys == {"cargo_toml", "ic", "rank_fixture_provenance", "rho"}
        sources = check_protocol.sources()
        inputs = check_protocol.inputs()
        assert set(sources) == set(freeze["source_sha256"])
        assert set(inputs) == set(freeze["input_sha256"])
        for key, path in {**sources, **inputs}.items():
            expected = (freeze["source_sha256"].get(key)
                        or freeze["input_sha256"].get(key))
            commit = release_commit if key in release_keys else archive_commit
            relative = path.relative_to(root).as_posix()
            data = blob(repo, commit, relative)
            assert sha(data) == expected, (key, commit, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        assert sha((experiment / "PROTOCOL.md").read_bytes()) == freeze["protocol_sha256"]
        bundle = experiment / "evidence"
        assert sha((bundle / "evidence.tar.gz").read_bytes()) == source["archive_sha256"]
        assert sha((bundle / "panel.json").read_bytes()) == source["panel_sha256"]
        import verify_archive  # type: ignore[import-not-found]

        manifest = json.loads((bundle / "archive_manifest.json").read_text())
        assert manifest["archive_sha256"] == source["archive_sha256"]
        assert manifest["panel_sha256"] == source["panel_sha256"]
        assert manifest["archive_bytes"] == (bundle / "evidence.tar.gz").stat().st_size
        sealed = root / "sealed"
        sealed.mkdir()
        assert verify_archive.unpack_checked(bundle / "evidence.tar.gz", sealed) == manifest["files"]
        panel_dir = sealed / "panel"
        assert (panel_dir / "panel.json").read_bytes() == (bundle / "panel.json").read_bytes()
        panel = json.loads((panel_dir / "panel.json").read_text())
        assert panel["classification"] == "COMPLETE_FIXED_STREAM_NO_CROSSOVER"
        assert panel["classification"] == manifest["classification"]
        assert panel["source_sha256"] == freeze["source_sha256"]
        assert panel["protocol_sha256"] == freeze["protocol_sha256"]
        assert panel["points_sha256"] == freeze["input_sha256"]["target_points"]
        assert panel["base_gzip_sha256"] == freeze["input_sha256"]["certified_base_gzip"]
        assert panel["validator_manifest_sha256"] == freeze["input_sha256"]["validator_manifest"]
        assert panel["release_main_head"] == freeze["release_main_head"]
        subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor",
                        panel["release_main_head"], panel["dispatch_main_head"]], check=True)
        assert panel["github_run_id"] == "36218536407"
        assert panel["github_run_attempt"] == "1"
        verify_archive.check_receipts(panel_dir, panel, freeze)
        assert all(step["returncode"] == 0 and not step["timed_out"]
                   and not step["rss_gate"] for step in panel["steps"].values())
        training_manifest = json.loads((panel_dir / "training/manifest.json").read_text())
        assert "KIC_FACTOR_BASE_JSONL" not in training_manifest["environment"]
        assert training_manifest["environment"]["KIC_FACTOR_BASE_SELECTION"] == "legacy_rank_fixture_lcg_v1"
        base_report = json.loads((panel_dir / "training/base_materialization.json").read_text())
        assert base_report["classification"] == "FRESH_BASE_MATCHES_CERTIFIED_ARM"
        assert base_report["fresh_header_sha256"] == sha(
            (panel_dir / "training/base_header.jsonl").read_bytes())
        assert panel["fresh_base_header_sha256"] == base_report["fresh_header_sha256"]
        receipt = audit_panel(experiment, panel_dir)
        receipt["archive_sha256"] = source["archive_sha256"]
        costs = panel["costs"]
        steps = panel["steps"]
        operational_ms = sum(steps[key]["wall_ms"] for key in (
            "training_producer", "base_materialization", "operational_rank",
            "ic", "operational_recovery"))
        assert math.isclose(operational_ms, costs["ic_operational_wall_ms"])
        assert math.isclose(operational_ms / steps["rho"]["wall_ms"],
                            costs["operational_ratio_to_rho"])
        assert math.isclose(steps["rho"]["wall_ms"], costs["rho_operational_wall_ms"])
        necessary_setup_ms = sum(steps[key]["wall_ms"] for key in (
            "training_producer", "base_materialization", "operational_rank"))
        assert necessary_setup_ms > costs["rho_operational_wall_ms"]
        output = {
            "schema": "n53-l384-archive-replay-v1",
            "archive_commit": archive_commit,
            "release_commit": release_commit,
            "archive_sha256": source["archive_sha256"],
            "panel_sha256": source["panel_sha256"],
            "classification": panel["classification"],
            "github_run_id": panel["github_run_id"],
            "github_run_attempt": panel["github_run_attempt"],
            "base_hash": panel["base_hash"],
            "ic_operational_wall_ms": costs["ic_operational_wall_ms"],
            "rho_operational_wall_ms": costs["rho_operational_wall_ms"],
            "necessary_setup_wall_ms": necessary_setup_ms,
            "operational_ratio_to_rho": costs["operational_ratio_to_rho"],
            "replay": receipt,
        }
    encoded = json.dumps(output, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
