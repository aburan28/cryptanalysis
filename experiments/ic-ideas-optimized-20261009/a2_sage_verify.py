#!/usr/bin/env python3
"""Independently replay every indexed N23 sparse support in checked Sage."""
from __future__ import annotations

import gzip
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007"
sys.path.insert(0, str(PRIOR))
from sage_probes import bits, field, from_bits  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "a2_sage_verify.json"
    if output.exists():
        raise FileExistsError(output)
    receipt_path = HERE / "a2_sparse_membership.json"
    index = json.loads(receipt_path.read_text())
    K, modulus = field(23)
    assert modulus == index["field_modulus_bits"]
    gamma = from_bits(K, index["gamma_bits"])
    assert gamma**47 == 1 and gamma != 1
    powers = [gamma**i for i in range(47)]
    support_path = HERE / "a2_sparse_membership.supports.gz"
    raw = gzip.decompress(support_path.read_bytes())
    assert len(raw) == 7 * 17_296
    checked = 0
    for value, a, b, c in struct.iter_unpack("<IBBB", raw):
        support = (a, b) if c == 255 else (a, b, c)
        observed = sum((powers[i] for i in support), K(0))
        assert bits(observed) == value
        checked += 1
    assert checked == 17_296
    result = {"schema_version": 1, "proposal_id": "A2",
              "candidate_id": None, "run_id": None,
              "status": "all_sparse_supports_replayed",
              "field_modulus_bits": modulus,
              "gamma_bits": index["gamma_bits"],
              "checked_supports": checked,
              "membership_receipt_sha256": sha(receipt_path),
              "supports_gzip_sha256": sha(support_path),
              "source_sha256": sha(Path(__file__)),
              "sage_probes_source_sha256": sha(PRIOR / "sage_probes.py")}
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "checked": checked}))


if __name__ == "__main__":
    main()
