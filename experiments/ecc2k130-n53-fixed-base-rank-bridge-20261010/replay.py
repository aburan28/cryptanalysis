#!/usr/bin/env python3
"""Replay the pinned crypto n53 full-rank held-out evidence without changing its checkout."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile


HERE = Path(__file__).resolve().parent
SOURCE = json.loads((HERE / "source.json").read_text())
RANK_VERIFIER = "research/notes/ecc2k130/compact_orbit_rank_evidence_20260929/verify_rank.py"
ARITHMETIC_VERIFIER = (
    "research/sat_factor_base_review_20260908/"
    "autolab_orbit_extract_20260924/independent_replay.py"
)
REGISTRY = "docs/curves/registry.json"
IC_SOURCE = "examples/koblitz_orbit_dlp_fast_online.rs"
RHO_SOURCE = "examples/koblitz_rho_batch_ks_strong_online.rs"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def checked_archive(repo: Path, destination: Path) -> None:
    commit = SOURCE["upstream_commit"]
    resolved = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--verify", commit + "^{commit}"],
        text=True,
    ).strip()
    assert resolved == commit, (resolved, commit)
    paths = [
        SOURCE["experiment_dir"],
        RANK_VERIFIER,
        ARITHMETIC_VERIFIER,
        REGISTRY,
        IC_SOURCE,
        RHO_SOURCE,
        "Cargo.lock",
    ]
    archive = subprocess.check_output(
        ["git", "-C", str(repo), "archive", "--format=tar", commit, *paths]
    )
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for member in tar:
            relative = PurePosixPath(member.name)
            assert not relative.is_absolute() and ".." not in relative.parts
            path = destination.joinpath(*relative.parts)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                path.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, path.open("wb") as target:
                    assert source is not None
                    shutil.copyfileobj(source, target)
            else:
                raise AssertionError(("unexpected Git archive entry", member.name))


def replay(command: list[str], output: Path, published: Path) -> dict:
    assert not output.exists()
    subprocess.run([sys.executable, *command, "--out", str(output)], check=True,
                   stdout=subprocess.DEVNULL)
    actual = load(output)
    assert actual == load(published), ("replay differs", published)
    assert actual["status"] == "PASS", published
    return actual


def check_identity(root: Path, experiment: Path, frozen: dict, heldout: dict) -> None:
    assert sha(root / REGISTRY) == SOURCE["registry_sha256"]
    assert sha(root / RANK_VERIFIER) == SOURCE["rank_verifier_sha256"]
    assert sha(root / ARITHMETIC_VERIFIER) == SOURCE["arithmetic_verifier_sha256"]
    assert sha(experiment / "analyze_heldout.py") == SOURCE["analyzer_sha256"]
    assert sha(root / IC_SOURCE) == heldout["ic_source_sha256"] == frozen["source_sha256"]
    assert sha(root / RHO_SOURCE) == heldout["rho_source_sha256"]
    assert sha(root / "Cargo.lock") == frozen["cargo_lock_sha256"]
    assert sha(experiment / "PROTOCOL.md") == frozen["protocol_sha256"]
    assert sha(experiment / "run_heldout.py") == heldout["runner_sha256"]
    assert sha(experiment / "verify_public_target.py") == heldout["ic_verifier_sha256"]
    assert sha(experiment / "verify_rho_public.py") == heldout["rho_verifier_sha256"]
    assert sha(experiment / "inputs/heldout_q.jsonl") == heldout["public_point_sha256"]
    assert sha(experiment / "inputs/heldout_fixture_verifier_only.jsonl") == (
        heldout["fixture_verifier_only_sha256"]
    )
    assert heldout["ic_binary_sha256"] == frozen["binary_sha256"]
    assert heldout["resource_envelope"] == frozen["resource_envelope"]

    candidate_records = {}
    for label in ("control", "cap400000"):
        candidate = load(experiment / f"candidate_{label}.json")
        identity = candidate["candidate_id"]
        assert identity == heldout["ic_candidate_ids"][label]
        assert identity.endswith("h" + canonical_digest(candidate["record"])[:12])
        candidate_records[label] = candidate["record"]
    assert candidate_records["control"]["factor_base"] == (
        candidate_records["cap400000"]["factor_base"]
    )
    assert candidate_records["control"]["factor_base"]["B"] == 23320
    assert candidate_records["control"]["factor_base"]["effective_columns"] == 220
    assert candidate_records["control"]["factor_base"]["base_hash_blake3"] == (
        frozen["base_hash_blake3"]
    )

    curve = candidate_records["control"]["curve"]
    registry = load(root / REGISTRY)
    matches = [
        (entry, representation)
        for entry in registry["curves"]
        for representation in entry.get("representations", [])
        if representation.get("ec1") == curve["curve_id"]
    ]
    assert len(matches) == 1
    registry_curve, representation = matches[0]
    curve_record_digest = canonical_digest(
        {"field": representation["field"], "curve": representation["curve"]}
    )
    assert curve_record_digest[:12] == curve["curve_id"][-12:]
    assert representation["curve_uid"].endswith(curve_record_digest)
    assert representation["field"] == candidate_records["control"]["field"]
    assert all(curve[key] == value for key, value in representation["curve"].items())
    assert int(registry_curve["order"]) == curve["order"]
    assert registry_curve["trace"] == curve["trace"]

    q = load(experiment / "inputs/heldout_q.jsonl")
    assert q == heldout["public_point"]
    assert len(heldout["rank_seeds"]) == len(heldout["rho_seeds"]) == 6
    for rank_seed, rho_seed in zip(heldout["rank_seeds"], heldout["rho_seeds"]):
        workload = load(experiment / f"heldout_workload_{rank_seed}.json")
        assert workload["workload_id"] == heldout["workload_ids"][str(rank_seed)]
        assert workload["workload_id"] == "W" + canonical_digest(workload["record"])[:12]
        assert workload["record"]["target"] == q
        assert workload["record"]["rank_seed"] == rank_seed
        assert workload["record"]["rho_seed"] == rho_seed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crypto-repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="n53-bridge-") as temporary:
        root = Path(temporary)
        checked_archive(args.crypto_repo, root)
        experiment = root / SOURCE["experiment_dir"]
        frozen = load(experiment / "FROZEN.json")
        heldout = load(experiment / "HELDOUT_FROZEN.json")
        check_identity(root, experiment, frozen, heldout)
        analysis_process = subprocess.run(
            [sys.executable, str(experiment / "analyze_heldout.py")],
            cwd=root, check=True, capture_output=True, text=True,
        )
        assert load(experiment / "HELDOUT_ANALYSIS.json")["status"] == "PASS"
        assert json.loads(analysis_process.stdout)["status"] == "PASS"
        analysis = load(experiment / "HELDOUT_ANALYSIS.json")
        assert sha(experiment / "HELDOUT_ANALYSIS.json") == SOURCE["analysis_sha256"]
        assert len(analysis["cells"]) == 18
        assert all(cell["status"] == "VERIFIED" for cell in analysis["cells"])
        assert analysis["controlled_online_speedup"] is None
        assert analysis["public_target"] == heldout["public_point"]
        assert analysis["base_hash_blake3"] == frozen["base_hash_blake3"]
        assert analysis["candidate_ids"] == heldout["ic_candidate_ids"]

        replay_dir = root / "new-replays"
        replay_dir.mkdir()
        rank_replays = target_replays = rho_replays = 0
        scalar = analysis["independently_replayed_scalar"]
        q_path = experiment / "inputs/heldout_q.jsonl"
        fixture = experiment / "inputs/heldout_fixture_verifier_only.jsonl"
        for rank_seed, rho_seed in zip(heldout["rank_seeds"], heldout["rho_seeds"]):
            for label in ("control", "cap400000"):
                directory = experiment / "runs/heldout" / str(rank_seed) / label
                rank = replay(
                    [str(root / RANK_VERIFIER),
                     "--trace", str(directory / "rank.jsonl"),
                     "--base", str(directory / "base.jsonl"),
                     "--summary", str(directory / "summary.jsonl")],
                    replay_dir / f"{rank_seed}-{label}-rank.json",
                    directory / "rank_replay.json",
                )
                assert rank["rank"] == rank["representative_logs_verified"] == 220
                rank_replays += 1
                target = replay(
                    [str(experiment / "verify_public_target.py"),
                     "--base", str(directory / "base.jsonl"),
                     "--target", str(directory / "targets.jsonl"),
                     "--expected-q", str(q_path)],
                    replay_dir / f"{rank_seed}-{label}-target.json",
                    directory / "target_replay.json",
                )
                assert target["recovered_scalar"] == scalar
                target_replays += 1
            rho_dir = experiment / "runs/heldout" / str(rank_seed) / "rho"
            rho = replay(
                [str(experiment / "verify_rho_public.py"),
                 "--rho", str(rho_dir / "rho.jsonl"),
                 "--public-point", str(q_path),
                 "--verifier-fixture", str(fixture),
                 "--seed", str(rho_seed)],
                replay_dir / f"{rank_seed}-rho.json",
                rho_dir / "rho_replay.json",
            )
            assert rho["recovered_scalar"] == scalar
            rho_replays += 1

        assert (rank_replays, target_replays, rho_replays) == (12, 12, 6)
        assert analysis["gate"]["all_18_cells_verified"] is True
        assert analysis["gate"]["passed"] is False
        cells = analysis["cells"]
        by_label = {
            label: [cell for cell in cells if cell["label"] == label]
            for label in ("control", "cap400000", "rho")
        }
        assert all(len(rows) == 6 for rows in by_label.values())
        receipt = {
            "schema": "n53-crypto-to-cryptanalysis-replay-v1",
            "status": "PASS",
            "upstream_commit": SOURCE["upstream_commit"],
            "analysis_sha256": SOURCE["analysis_sha256"],
            "public_target": heldout["public_point"],
            "recovered_scalar": scalar,
            "actual_factor_base_points": 23320,
            "folded_columns": 220,
            "base_hash_blake3": frozen["base_hash_blake3"],
            "candidate_ids": heldout["ic_candidate_ids"],
            "workload_ids": heldout["workload_ids"],
            "independent_rank_replays": rank_replays,
            "independent_target_replays": target_replays,
            "independent_rho_replays": rho_replays,
            "all_18_cells_verified": True,
            "median_control_cold_ms": statistics.median(
                row["cold_in_process_ms"] for row in by_label["control"]
            ),
            "median_cap400000_cold_ms": statistics.median(
                row["cold_in_process_ms"] for row in by_label["cap400000"]
            ),
            "median_control_online_ms": statistics.median(
                row["target_online_ms"] for row in by_label["control"]
            ),
            "median_cap400000_online_ms": statistics.median(
                row["target_online_ms"] for row in by_label["cap400000"]
            ),
            "median_rho_online_ms": statistics.median(
                row["rho_online_ms"] for row in by_label["rho"]
            ),
            "gate": analysis["gate"],
            "controlled_online_speedup": None,
        }
        encoded = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
        if args.out.exists():
            assert args.out.read_text() == encoded, "frozen bridge replay changed"
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(encoded)
        print(json.dumps({
            "status": receipt["status"],
            "independent_replays": [rank_replays, target_replays, rho_replays],
            "gate_passed": receipt["gate"]["passed"],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
