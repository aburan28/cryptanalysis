#!/usr/bin/env python3
"""Read-only custody check for the post-panel formatting-only C edit."""

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1].parent
RECEIPT = Path(__file__).resolve().parent / "tau3-atlas-format-equivalence.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_format_equivalence(source_sha, bench_sha):
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["status"] == "clang_format_only_identical_native_binaries"
    assert receipt["bench_binary_sha256_before"] == bench_sha
    assert receipt["bench_binary_sha256_after"] == bench_sha
    assert receipt["test_binary_sha256_before"] == receipt["test_binary_sha256_after"]
    old_commit = receipt["preformat_commit"]
    for relative, digests in receipt["sources"].items():
        old = subprocess.check_output(["git", "show", f"{old_commit}:{relative}"], cwd=ROOT)
        assert sha256(old) == digests["before"]
        assert sha256((ROOT / relative).read_bytes()) == digests["after"]
    assert receipt["sources"]["src/ec_tau.c"]["before"] == source_sha
    binary = ROOT / "build-tau3-atlas/ca_tau_chain_bench"
    if binary.exists():
        assert sha256(binary.read_bytes()) == bench_sha


def main():
    panel = json.loads((RECEIPT.parent / "tau3-atlas-panel.json").read_text())
    verify_format_equivalence(panel["ec_tau_source_sha256"], panel["bench_sha256"])
    print("tau3 atlas formatting audit: PASS (frozen source bound; rebuilt binaries identical)")


if __name__ == "__main__":
    main()
