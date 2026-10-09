"""Archive both exact F4 cache screens with byte-verified raw evidence."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
FIRST = "4884965ad6e9240170bfffa5b78bb7f319d65ee6"
SECOND = "ad6b75b26bca5f622f55c7a40a763df35bbf777d"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def add(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = info.uid = info.gid = 0
    info.uname = info.gname = ""
    tar.addfile(info, io.BytesIO(data))


def main():
    reference = BUILD / "reference/early-parity-validation-v4"
    ref_report = reference / "panel/report.json"
    ref = json.loads(ref_report.read_text())
    audit = json.loads((reference / "audit.json").read_text())
    assert ref["status"] in ("PASS", "RECORDED_PENDING_AUDIT")
    assert audit["status"] == "PASS" and audit["rows"] == 52
    files = {}
    for label, directory, commit in (
        ("fitcount-panel", BUILD / "panel", FIRST),
        ("fitcount-profile", BUILD / "paired-profile", FIRST),
        ("priority-panel", BUILD / "panel-priority", SECOND),
        ("priority-profile", BUILD / "paired-profile-priority", SECOND),
    ):
        report = json.loads((directory / "report.json").read_text())
        assert report["status"] == "PASS" and report["source_commit"] == commit
        assert len(report["rows"]) == (60 if "profile" in label else 10)
        assert all(row["execution"] == "completed" for row in report["rows"])
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                assert not path.is_symlink()
                files[f"{label}/{path.relative_to(directory)}"] = path.read_bytes()
    for label in ("large-proof", "large-proof-priority"):
        value = json.loads((BUILD / (label + ".json")).read_text())
        assert value["status"] == "PASS" and len(value["rows"]) == 7
        assert all(row["corrupted_output_rejected"] for row in value["rows"])
        files[label + ".json"] = (BUILD / (label + ".json")).read_bytes()
    for label in ("receipt-fitcount", "receipt"):
        value = json.loads((BUILD / (label + ".json")).read_text())
        assert value["source_commit"] == (FIRST if label.endswith("fitcount") else SECOND)
        files["build/" + label + ".json"] = (BUILD / (label + ".json")).read_bytes()
    for label in ("engine-fitcount.inc", "engine.inc"):
        files["build/" + label] = (BUILD / label).read_bytes()
    files["reference/report.json"] = ref_report.read_bytes()
    files["reference/audit.json"] = (reference / "audit.json").read_bytes()
    for row in ref["rows"]:
        if row["name"] not in {f"pdp-12-seed-{i}" for i in range(1, 6)}:
            continue
        if row["early_mode"] != 1:
            continue
        path = ref_report.parent / row["result"]
        assert sha(path.read_bytes()) == row["sha256"]
        files["reference/" + path.name] = path.read_bytes()
        proof = path.with_suffix(".gbp")
        files["reference/" + proof.name] = proof.read_bytes()
    root = HERE.parents[2]
    for path in sorted(HERE.glob("*.py")):
        files["sources/current/" + path.name] = path.read_bytes()
    for commit in (FIRST, SECOND):
        files["sources/" + commit + "/generate.py"] = subprocess.check_output(
            ["git", "show", f"{commit}:experiments/groebner-perf-20260924/round122/generate.py"],
            cwd=root)
    logical, objects = {}, {}
    for name, data in sorted(files.items()):
        digest = sha(data)
        logical[name] = {"sha256": digest, "bytes": len(data)}
        objects.setdefault(digest, data)
    manifest = dict(schema="f4-basis-metadata-evidence/1", commits=[FIRST, SECOND],
                    logical=logical)
    target = HERE / "results.tar.gz"
    staged = HERE / "results.tar.gz.tmp"
    assert not staged.exists()
    with staged.open("wb") as stream, gzip.GzipFile(filename="", mode="wb",
                                                    fileobj=stream, mtime=0) as packed:
        with tarfile.open(fileobj=packed, mode="w") as tar:
            add(tar, "manifest.json",
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode() + b"\n")
            for digest, data in sorted(objects.items()):
                add(tar, "objects/" + digest, data)
    decoded, read_manifest = {}, None
    with tarfile.open(staged, "r|gz") as tar:
        for member in tar:
            data = tar.extractfile(member).read()
            if member.name == "manifest.json":
                read_manifest = json.loads(data)
            else:
                digest = member.name.removeprefix("objects/")
                assert sha(data) == digest
                decoded[digest] = data
    assert read_manifest == manifest and set(decoded) == set(objects)
    assert all(decoded[entry["sha256"]] == files[name]
               for name, entry in logical.items())
    receipt = dict(status="PASS", archive=target.name, sha256=sha(staged.read_bytes()),
                   bytes=staged.stat().st_size, logical_files=len(logical),
                   distinct_objects=len(objects), lossless_byte_verification=True,
                   commits=[FIRST, SECOND], timing_eligible=False,
                   qualified_speedup=None)
    staged.replace(target)
    (HERE / "archive.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("F4_BASIS_METADATA_ARCHIVE_PASS", len(logical), len(objects), target.stat().st_size)


if __name__ == "__main__":
    main()
