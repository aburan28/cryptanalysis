#!/usr/bin/env python3
"""Bind Q1459 encoding, prepared XCNFs, and external solver source before builds."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPSTREAM = Path("/private/tmp/wdsat-q1458")
Q1458_BUILD = HERE.parent / "q20261011_wdsat_bridge" / "build.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prepared = json.loads((HERE / "prepare_receipt.json").read_text())
    assert prepared["protocol_sha256"] == sha(HERE / "protocol.json")
    assert prepared["source_sha256"] == sha(HERE / "prepare.py")
    assert prepared["witness_replay_status"] == "PASS"
    for cell in protocol["cells"]:
        assert sha(HERE / f"{cell}.xcnf.gz") == prepared["cells"][cell]["derived_archive_sha256"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM,
                                     text=True).strip()
    assert commit == protocol["upstream_solver"]["commit"]
    assert not subprocess.check_output(["git", "status", "--porcelain"],
                                       cwd=UPSTREAM).strip()
    output = {"proposal_id": "Q1459", "candidate_id": None,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "prepare_receipt_sha256": sha(HERE / "prepare_receipt.json"),
              "prepare_source_sha256": sha(HERE / "prepare.py"),
              "build_source_sha256": sha(HERE / "build.py"),
              "shared_patch_source_sha256": sha(Q1458_BUILD),
              "upstream_commit": commit,
              "upstream_tree_sha256": subprocess.check_output(
                  ["git", "rev-parse", "HEAD^{tree}"], cwd=UPSTREAM,
                  text=True).strip()}
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2,
                                                  sort_keys=True) + "\n")
    print("FROZEN Q1459", commit)


if __name__ == "__main__":
    main()
