#!/usr/bin/env python3
"""Package only tracked, source-hashed files for one serialized Linux replay."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "experiments/prime-j0-host-replay-20261010"))
import host_replay as replay

EXTRA = (
    "PROTOCOL.md", "PROOF.md", "ISOLATED_PANEL.md", "make_inputs.py",
    "fresh-inputs.json", "verify_candidate.py", "make_isolated_manifests.py",
    "runpod_correctness.sh", "stage_source.py",
)


def add_bytes(archive, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    archive.addfile(info, io.BytesIO(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("source archive already exists")
    paths = set(replay.source_paths("sector"))
    paths.update(HERE / name for name in EXTRA)
    relative = sorted(str(path.relative_to(ROOT)) for path in paths)
    subprocess.run(["git", "ls-files", "--error-unmatch", "--", *relative],
                   cwd=ROOT, stdout=subprocess.DEVNULL, check=True)
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", *relative],
                   cwd=ROOT, stdout=subprocess.DEVNULL, check=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                     cwd=ROOT, text=True).strip()
    index = "".join(f"{replay.sha(ROOT / name)}  source/{name}\n" for name in relative)
    with tarfile.open(output, "w") as archive:
        for name in relative:
            add_bytes(archive, "source/" + name, (ROOT / name).read_bytes())
        add_bytes(archive, "source-files.sha256", index.encode())
        add_bytes(archive, "source-commit.txt", (commit + "\n").encode())
    print(json.dumps({"commit": commit, "files": len(relative),
                      "archive": str(output), "archive_sha256": replay.sha(output),
                      "index_sha256": hashlib.sha256(index.encode()).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
