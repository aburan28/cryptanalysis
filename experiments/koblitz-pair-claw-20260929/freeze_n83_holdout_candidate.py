#!/usr/bin/env python3
"""Name the exact x86 quotient-table pipeline for the fresh holdout."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE / "candidates" / (
    "IC1N83Ckb1fb8000204PDP4qtableRCdirectLAnoneTDdirectISO0hd66302fd58d2.json")
RUNNER = HERE / "run_n83_holdout_chunk.py"
VERIFIER = HERE / "verify_n83_holdout_receipt_sage.py"
UPSTREAM = HERE / "verify_n83_quotient_receipt_sage.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main():
    candidate = json.loads(PRIOR.read_text())
    assert candidate["candidate_record_sha256"] == hashlib.sha256(
        canonical({k: v for k, v in candidate.items() if k not in (
            "candidate_id", "candidate_record_sha256")})).hexdigest()
    candidate.pop("candidate_id")
    candidate.pop("candidate_record_sha256")
    candidate["point_decomposition"]["filter"] = {
        "bits_per_key": 20, "hashes": 10}
    candidate["relation_collection"]["implementation_sha256"] = sha(RUNNER)
    candidate["target_descent"]["implementation_sha256"] = sha(RUNNER)
    candidate["implementation"]["wrapper_source_sha256"] = sha(RUNNER)
    candidate["implementation"]["independent_verifier_source_sha256"] = sha(
        VERIFIER)
    candidate["implementation"]["sage_verifier_core_source_sha256"] = sha(
        UPSTREAM)
    digest = hashlib.sha256(canonical(candidate)).hexdigest()
    label = f"IC1N83Ckb1fb8000204PDP4qtableRCdirectLAnoneTDdirectISO0h{digest[:12]}"
    candidate["candidate_id"] = label
    candidate["candidate_record_sha256"] = digest
    path = HERE / "candidates" / f"{label}.json"
    content = json.dumps(candidate, indent=2) + "\n"
    if path.exists():
        assert path.read_text() == content
    else:
        path.write_text(content)
    print(json.dumps({"candidate_id": label, "manifest": str(path),
                      "manifest_sha256": sha(path)}))


if __name__ == "__main__":
    main()
