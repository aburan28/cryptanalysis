#!/usr/bin/env python3
"""Archive and hash the source-bound receipts of the fresh n83 solve."""

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
Q1091 = RUNS / "q1091_raw_ci_37069216423"
ARCHIVE = HERE / "n83_fresh_terminal_evidence.tar.gz"
MANIFEST = HERE / "n83_fresh_terminal_evidence_manifest.json"
LOCAL_NAMES = ("n83_q1093_local_arm_m32_r30",
               "n83_q1093_second_local_arm_m32_r30")
LOCAL_PREFIXES = ("n83_q1093_m32_r30", "n83_q1093_second_m32_r30")


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes())


def sources():
    entries = {}

    def add(name, path):
        assert name not in entries and path.is_file(), (name, path)
        entries[name] = path

    for name in ("workflow_run_terminal_20261003T1903Z.json",
                 "workflow_snapshot.yml", "sage_runtime_info.json"):
        add(f"q1091/{name}", Q1091 / name)
    for shard in range(56):
        add(f"q1091/audits/shard-{shard}.json",
            Q1091 / f"audits/shard-{shard}.json")
        artifact = Q1091 / f"n83-q1091-holdout-M32-R29-shard-{shard}"
        assert artifact.is_dir()
        for path in sorted(artifact.rglob("*")):
            if path.is_file():
                add(f"q1091/artifacts/shard-{shard}/{path.relative_to(artifact)}",
                    path)
    for label, name, prefix in zip(("first", "second"), LOCAL_NAMES,
                                   LOCAL_PREFIXES):
        for suffix, renamed in ((".json", "receipt.json"),
                                ("_sage_verify.json", "sage_verify.json"),
                                ("_runtime_info.json", "runtime_info.json"),
                                ("_preflight.json", "preflight.json"),
                                (".launch.log", "launch.log")):
            add(f"q1093/{label}/{renamed}", RUNS / (name + suffix))
        add(f"q1093/{label}/native_binary",
            Path("/private/tmp") / (prefix + "_native"))
        source_dir = Path("/private/tmp") / (prefix + "_sources")
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                add(f"q1093/{label}/sources/{path.relative_to(source_dir)}",
                    path)
    for name in ("n83_q1091_terminal_reconciliation.json",
                 "n83_fresh_terminal_extended_capacity.json",
                 "n83_q1091_terminal_30day_cycle_envelope.json"):
        add(f"results/{name}", HERE / name)
    return dict(sorted(entries.items()))


def freeze():
    assert not ARCHIVE.exists() and not MANIFEST.exists()
    files = sources()
    rows = []
    with ARCHIVE.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0,
                           compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, path in files.items():
                    data = path.read_bytes()
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mtime = 0
                    info.mode = 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    archive.addfile(info, io.BytesIO(data))
                    rows.append({"path": name, "bytes": len(data),
                                 "sha256": sha_bytes(data)})
    report = {
        "kind": "n83_fresh_terminal_source_bound_evidence_archive",
        "curve_id": "EC1N83Ckb1h876c2921cb64",
        "workload_id": "9ccc27baec79",
        "verified_fresh_target_scalar": "1228047131163538399404643",
        "Q1091_successful_artifacts": 56,
        "Q1091_terminal_jobs": 64,
        "local_Q1093_terminal_jobs": 2,
        "archive_name": ARCHIVE.name,
        "archive_sha256": sha(ARCHIVE),
        "archive_bytes": ARCHIVE.stat().st_size,
        "file_count": len(rows),
        "files": rows,
        "source_sha256": sha(Path(__file__)),
    }
    MANIFEST.write_text(json.dumps(report, indent=2) + "\n")
    verify()
    return report


def verify():
    report = json.loads(MANIFEST.read_text())
    assert report["archive_sha256"] == sha(ARCHIVE)
    assert report["archive_bytes"] == ARCHIVE.stat().st_size
    assert report["source_sha256"] == sha(Path(__file__))
    expected = {row["path"]: row for row in report["files"]}
    assert len(expected) == report["file_count"]
    with tarfile.open(ARCHIVE, mode="r:gz") as archive:
        actual = {}
        for member in archive:
            assert member.isfile() and member.name in expected
            data = archive.extractfile(member).read()
            assert len(data) == expected[member.name]["bytes"]
            assert sha_bytes(data) == expected[member.name]["sha256"]
            actual[member.name] = True
    assert set(actual) == set(expected)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    report = verify() if args.verify else freeze()
    print(json.dumps({"file_count": report["file_count"],
                      "archive_bytes": report["archive_bytes"],
                      "archive_sha256": report["archive_sha256"]}))


if __name__ == "__main__":
    main()
