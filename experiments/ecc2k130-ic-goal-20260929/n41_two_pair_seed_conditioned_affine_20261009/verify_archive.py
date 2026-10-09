#!/usr/bin/env python3
"""Verify exact compressed rank witnesses against the Sage audit receipt."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    protocol_raw = (HERE / "protocol.json").read_bytes()
    audit = json.loads((HERE / "audit.json").read_text())
    raw = gzip.decompress((HERE / "result.json.gz").read_bytes())
    result = json.loads(raw)
    if (sha(raw) != audit["result_sha256"] or
            sha(protocol_raw) != audit["protocol_sha256"] or
            sha((HERE / "sage_runtime_info.json").read_bytes()) != audit["runtime_sha256"] or
            result["protocol_sha256"] != audit["protocol_sha256"] or
            result["status"] != "COMPLETE_ALL_SEED_BINS" or
            audit["status"] != "PASS_INDEPENDENT_SAGE_AFFINE_BIN_RANK_AUDIT" or
            result["sign_orbits_scanned"] != audit["sign_orbits_recounted"] != 1583568 or
            len(result["bin_records"]) != audit["seed_sum_pair_bins"] != 3969 or
            result["deficient_bins"] != audit["deficient_bins"] != 0 or
            sum(len(cell["witnesses"]) for cell in result["bin_records"].values()) !=
            audit["independent_group_rank_witnesses"] != 162729 or
            any(cell["rank"] != 41 for cell in result["bin_records"].values())):
        raise ValueError("compressed rank receipt differs from independent Sage audit")
    print("PASS_ARCHIVED_AFFINE_RANK_RECEIPT")


if __name__ == "__main__":
    main()
