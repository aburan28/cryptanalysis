"""Preserve exact local F4 batch evidence in a verified content-addressed archive."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def add(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    tar.addfile(info, io.BytesIO(data))


def main():
    parser = argparse.ArgumentParser()
    for name in ("inner", "panel", "profile", "large", "reference_report", "failed_batch"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    inner = json.loads((args.inner / "report.json").read_text())
    panel = json.loads((args.panel / "report.json").read_text())
    profile = json.loads((args.profile / "report.json").read_text())
    large = json.loads(args.large.read_text())
    reference = json.loads(args.reference_report.read_text())
    failed_batch = json.loads(args.failed_batch.read_text())
    audit_path = args.reference_report.parent.parent / "audit.json"
    audit = json.loads(audit_path.read_text())
    assert (inner["status"] == panel["status"] == profile["status"]
            == large["status"] == audit["status"] == "PASS")
    assert len(inner["rows"]) == 30 and len(panel["rows"]) == 10
    assert len(profile["rows"]) == 60 and len(large["rows"]) == 3
    assert audit["rows"] == 52 and all(row["corrupted_output_rejected"]
                                       for row in large["rows"])
    assert failed_batch["result"]["status"] == "inconclusive"
    assert failed_batch["result"]["work"] == 79_999_698
    assert inner["source_commit"] == panel["source_commit"] == profile["source_commit"]
    for row in profile["rows"]:
        assert row["execution"] == "completed" and row["assignment"] is not None
    assert all(row["execution"] == "completed" for row in panel["rows"] + inner["rows"])
    sources = {}
    for label in ("inner", "panel", "profile"):
        directory = getattr(args, label)
        assert directory.is_dir() and not directory.is_symlink()
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                assert not path.is_symlink()
                sources[f"{label}/{path.relative_to(directory)}"] = path
    for label in ("large", "failed_batch", "reference_report", "reference_audit"):
        path = audit_path if label == "reference_audit" else getattr(args, label)
        assert path.is_file() and not path.is_symlink()
        sources[label + ".json"] = path
    # Retain the five frozen hard-case inputs and their proof certificates.
    for row in reference["rows"]:
        if row["name"] not in {f"pdp-12-seed-{seed}" for seed in range(1, 6)}:
            continue
        if row["early_mode"] != 1:
            continue
        path = args.reference_report.parent / row["result"]
        assert digest(path.read_bytes()) == row["sha256"]
        sources[f"reference/{path.name}"] = path
        proof = path.with_suffix(".gbp")
        assert proof.is_file()
        sources[f"reference/{proof.name}"] = proof
    for label in ("round115", "round116"):
        directory = HERE.parent / label
        for path in sorted(directory.glob("*.py")):
            sources[f"sources/{label}/{path.name}"] = path
        sources[f"build/{label}-receipt.json"] = directory / "build/receipt.json"
    logical, objects = {}, {}
    for name, path in sorted(sources.items()):
        data = path.read_bytes()
        hash_value = digest(data)
        logical[name] = {"sha256": hash_value, "bytes": len(data)}
        objects.setdefault(hash_value, data)
    manifest = {
        "schema": "f4-initial-batch-evidence/1",
        "experiment_commit": panel["source_commit"],
        "reports": ["inner/report.json", "panel/report.json", "profile/report.json",
                    "large.json", "failed_batch.json", "reference_report.json",
                    "reference_audit.json"],
        "logical": logical,
    }
    target = HERE / "results.tar.gz"
    staged = HERE / "results.tar.gz.tmp"
    assert not staged.exists()
    with staged.open("wb") as stream, gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                                                     mtime=0) as packed:
        with tarfile.open(fileobj=packed, mode="w") as tar:
            add(tar, "manifest.json",
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode() + b"\n")
            for hash_value, data in sorted(objects.items()):
                add(tar, "objects/" + hash_value, data)
    decoded, read_manifest = {}, None
    with tarfile.open(staged, "r|gz") as tar:
        for member in tar:
            data = tar.extractfile(member).read()
            if member.name == "manifest.json":
                read_manifest = json.loads(data)
            else:
                hash_value = member.name.removeprefix("objects/")
                assert digest(data) == hash_value
                decoded[hash_value] = data
    assert read_manifest == manifest and set(decoded) == set(objects)
    for name, entry in logical.items():
        assert decoded[entry["sha256"]] == sources[name].read_bytes()
    receipt = {
        "status": "PASS", "archive": target.name, "sha256": digest(staged.read_bytes()),
        "bytes": staged.stat().st_size, "logical_files": len(logical),
        "distinct_objects": len(objects), "lossless_byte_verification": True,
        "experiment_commit": panel["source_commit"], "qualified_speedup": None,
    }
    staged.replace(target)
    (HERE / "archive.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("F4_INITIAL_BATCH_ARCHIVE_PASS", len(logical), len(objects), target.stat().st_size)


if __name__ == "__main__":
    main()
