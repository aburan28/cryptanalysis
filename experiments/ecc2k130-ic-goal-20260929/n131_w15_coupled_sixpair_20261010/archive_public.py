#!/usr/bin/env python3
"""Copy the frozen W15 public-query raw artifacts from local temp to the repo."""

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = Path("/private/tmp/n131_w15_coupled_sixpair_public_20261010")
DEST = HERE / "public_query"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    audit = json.loads((HERE / "terminal_audit.json").read_text())
    result = json.loads((SOURCE / "result.json").read_text())
    assert audit["status"] == "PASS_W15_N131_TERMINAL_AUDIT"
    assert audit["source_sha256"]["public_result"] == sha(SOURCE / "result.json")
    names = ["result.json", "system.xcnf.gz", "solver.stdout.txt", "solver.stderr.txt"]
    if (SOURCE / "group_lift.json").exists():
        names.append("group_lift.json")
    assert not DEST.exists()
    DEST.mkdir()
    for name in names:
        shutil.copyfile(SOURCE / name, DEST / name)
        assert sha(SOURCE / name) == sha(DEST / name)
    receipt = {
        "status": "PASS_W15_PUBLIC_QUERY_ARCHIVE",
        "candidate_id": None,
        "curve_id": result["curve_id"],
        "target_q": result["target_q"],
        "query_status": result["status"],
        "source_dir": str(SOURCE),
        "archive_dir": str(DEST),
        "source_sha256": {
            "script": sha(__file__),
            "terminal_audit": sha(HERE / "terminal_audit.json"),
            **{name: sha(DEST / name) for name in names},
        },
        "bytes": {name: (DEST / name).stat().st_size for name in names},
    }
    with (HERE / "archive_receipt.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "query_status": result["status"],
                      "archived_bytes": sum(receipt["bytes"].values())}))


if __name__ == "__main__":
    main()
