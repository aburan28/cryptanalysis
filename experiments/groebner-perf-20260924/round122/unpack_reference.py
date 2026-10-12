"""Materialize the frozen independently audited round112 panel for replay."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
PREFIX = "early-parity-validation-v4/"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    archive = HERE.parent / "round112/results.tar.gz"
    receipt = json.loads((HERE.parent / "round112/archive.json").read_text())
    assert receipt["status"] == "PASS"
    assert sha(archive.read_bytes()) == receipt["sha256"]
    assert not args.output.exists()
    with tarfile.open(archive, "r:gz") as packed:
        manifest = json.load(packed.extractfile("manifest.json"))
        wanted = {name: item for name, item in manifest["logical"].items()
                  if name.startswith(PREFIX)}
        assert "early-parity-validation-v4/audit.json" in wanted
        assert "early-parity-validation-v4/panel/report.json" in wanted
        for seed in range(1, 6):
            assert f"early-parity-validation-v4/panel/pdp-12-seed-{seed}-early1.json" in wanted
        args.output.mkdir(parents=True)
        for name, item in sorted(wanted.items()):
            data = packed.extractfile("objects/" + item["sha256"]).read()
            assert sha(data) == item["sha256"] and len(data) == item["bytes"]
            target = args.output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    audit = json.loads((args.output / "early-parity-validation-v4/audit.json").read_text())
    report = json.loads((args.output / "early-parity-validation-v4/panel/report.json").read_text())
    assert audit["status"] == "PASS" and audit["rows"] == 52
    assert report["status"] in ("PASS", "RECORDED_PENDING_AUDIT")
    print("F4_FITCACHE_REFERENCE_PASS", len(wanted), flush=True)


if __name__ == "__main__":
    main()
