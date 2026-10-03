#!/usr/bin/env python3
"""Archive the exact n83 known-log base as signed-Frobenius orbit keys.

The compressed keys define the full point set together with the exact curve
and sign/Frobenius action. The independent checked-Sage replay receipt proves
that the seeded representatives are subgroup points with the recorded logs.
"""

import base64
import hashlib
import json
from pathlib import Path

import fbarchive

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments/koblitz-pair-claw-20260929"
CANDIDATE = EXP / "candidates/IC1N83Ckb1fb8000204PDP4qtableRCdirectLAnoneTDdirectISO0h49b47d79e9e3.json"
RECEIPT = EXP / "runs/n83_knownlog_orbit_base_k48194.json"
REPLAY = EXP / "runs/n83_knownlog_orbit_base_k48194_verified.json"
BUILDER = EXP / "build_n83_knownlog_base_k48194.py"
VERIFIER = EXP / "verify_n83_knownlog_base_k48194.py"
SCHEMA = "ic-factor-base-orbit-archive/1"
KEY_BYTES = 21
RECORD_BYTES = 32
ORBIT_SIZE = 166


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def build_doc():
    candidate, receipt, replay = map(load, (CANDIDATE, RECEIPT, REPLAY))
    field, curve, base = (candidate[key] for key in
                          ("field", "curve", "factor_base"))
    assert field["p"] == 2 and field["n"] == 83
    assert curve["curve_id"] == receipt["curve_id"] == replay["curve_id"]
    assert candidate["isogeny"] == receipt["isogeny"] == replay["isogeny"] == "none"
    assert receipt["curve_identity_record"] == {
        "field": field,
        "curve": {k: v for k, v in curve.items() if k != "curve_id"},
    }
    curve_digest = hashlib.sha256(fbarchive.canonical(
        receipt["curve_identity_record"]).encode()).hexdigest()
    assert curve["curve_id"] == "EC1N83Ckb1h" + curve_digest[:12]
    candidate_record = {k: v for k, v in candidate.items() if k not in
                        ("candidate_id", "candidate_record_sha256")}
    candidate_digest = fbarchive.sha256_hex(candidate_record)
    assert candidate["candidate_record_sha256"] == candidate_digest
    assert candidate["candidate_id"].endswith("h" + candidate_digest[:12])
    assert all(receipt["factor_base"][key] == value
               for key, value in base.items())
    assert replay["all_checks_passed"] is True
    assert replay["base_receipt_sha256"] == sha(RECEIPT)
    assert receipt["source_sha256"] == sha(BUILDER)
    assert replay["verifier_source_sha256"] == sha(VERIFIER)
    assert replay["actual_B"] == base["actual_usable_points_B_before_folding"]
    assert replay["folded_columns"] == base["signed_frobenius_columns"]
    assert base["signed_frobenius_orbit_size"] == ORBIT_SIZE
    assert base["seed"] == 831043
    assert base["signed_frobenius_columns"] == 48194
    assert base["actual_usable_points_B_before_folding"] == 48194 * ORBIT_SIZE
    assert base["unknown_log_columns"] == 0
    key_file = EXP / receipt["factor_base"]["key_and_log_file"]
    raw = key_file.read_bytes()
    assert sha(key_file) == base["key_and_log_file_sha256"]
    assert len(raw) == base["key_and_log_file_bytes"] == 48194 * RECORD_BYTES
    keys = b"".join(raw[i:i + KEY_BYTES] for i in range(0, len(raw), RECORD_BYTES))
    assert hashlib.sha256(keys).hexdigest() == base["enumerated_set_sha256"]
    assert len(keys) == 48194 * KEY_BYTES
    key_ints = [int.from_bytes(keys[i:i + KEY_BYTES], "little")
                for i in range(0, len(keys), KEY_BYTES)]
    assert key_ints == sorted(set(key_ints))
    assert base["enumerated_set_encoding"].startswith("sorted canonical point keys")
    assert key_ints[-1] < 1 << 168
    return {
        "schema": SCHEMA,
        "field": field,
        "curve": curve,
        "isogeny": "none",
        "factor_base": base,
        "factor_base_sha256": fbarchive.sha256_hex(base),
        "orbit_representatives_b64": base64.b64encode(keys).decode("ascii"),
        "orbit_representative_count": len(key_ints),
        "orbit_key_bytes": KEY_BYTES,
        "orbit_size": ORBIT_SIZE,
        "expanded_point_count": len(key_ints) * ORBIT_SIZE,
        "point_set_encoding": "each sorted canonical key expands by 83 Frobenius powers and both signs on the declared n83 curve; keys are packed 21-byte little-endian integers",
        "expanded_points_materialized": False,
        "recipe": {"n": 83, "family": "knownlogorbit", "l": None,
                   "seed": base["seed"]},
        "source_sha256": {
            "candidate_manifest": sha(CANDIDATE),
            "base_receipt": sha(RECEIPT),
            "independent_sage_replay": sha(REPLAY),
            "base_builder": sha(BUILDER),
            "independent_sage_verifier": sha(VERIFIER),
            "representative_and_log_binary": sha(key_file),
            "archive_generator": sha(Path(__file__)),
        },
    }


def verify_doc(doc, row, rebuild=False):
    errors = []
    if doc.get("schema") != SCHEMA:
        return ["orbit archive schema mismatch"]
    rec = doc["factor_base"]
    try:
        keys = base64.b64decode(doc["orbit_representatives_b64"], validate=True)
        count = doc["orbit_representative_count"]
        width = doc["orbit_key_bytes"]
        assert width == KEY_BYTES and len(keys) == count * width
        values = [int.from_bytes(keys[i:i + width], "little")
                  for i in range(0, len(keys), width)]
        assert values == sorted(set(values))
        assert hashlib.sha256(keys).hexdigest() == rec["enumerated_set_sha256"]
        assert doc["orbit_size"] == rec["signed_frobenius_orbit_size"] == ORBIT_SIZE
        assert doc["expanded_point_count"] == rec[
            "actual_usable_points_B_before_folding"] == count * ORBIT_SIZE
        assert count == rec["signed_frobenius_columns"]
        assert doc["expanded_points_materialized"] is False
        assert doc["isogeny"] == "none"
        assert doc["field"]["n"] == 83
        assert doc["curve"]["curve_id"] == row["curve_id"]
        identity = {"field": doc["field"], "curve": {
            k: v for k, v in doc["curve"].items() if k != "curve_id"}}
        curve_digest = hashlib.sha256(fbarchive.canonical(identity).encode()).hexdigest()
        assert doc["curve"]["curve_id"] == "EC1N83Ckb1h" + curve_digest[:12]
        assert fbarchive.sha256_hex(rec) == doc["factor_base_sha256"] == row[
            "factor_base_sha256"]
        assert rec["enumerated_set_sha256"] == row["enumerated_set_sha256"]
        assert str(count * ORBIT_SIZE) == row["fb_points"]
        assert str(count) == row["effective_columns"]
        assert row["points_included"] == "orbit-compressed"
        assert row["l"] == "" and doc["recipe"]["l"] is None
        if rebuild:
            assert fbarchive.canonical(build_doc()) == fbarchive.canonical(doc)
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"{row['path']}: compressed orbit set or source rebuild differs: {exc}")
    return errors


def store_doc(doc):
    content = fbarchive.canonical(doc).encode("utf-8")
    blob = fbarchive.compress(content, "gz")
    rec = doc["factor_base"]
    name = f"knownlogorbit-s{rec['seed']}-{doc['factor_base_sha256'][:12]}.json.gz"
    rel = Path("bases") / doc["curve"]["curve_id"] / name
    if len(blob) > fbarchive.MAX_GIT_BYTES:
        raise ValueError("compressed orbit archive exceeds the git archive limit")
    path = fbarchive.HERE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == blob, "immutable archive differs"
    else:
        path.write_bytes(blob)
    row = {
        "factor_base_sha256": doc["factor_base_sha256"],
        "curve_id": doc["curve"]["curve_id"], "n": 83,
        "family": "knownlogorbit", "l": "", "seed": rec["seed"],
        "fb_points": doc["expanded_point_count"],
        "geometric_points": doc["expanded_point_count"],
        "effective_columns": doc["orbit_representative_count"],
        "strict_points": doc["expanded_point_count"],
        "quotient_rule": "sign+frobenius",
        "points_included": "orbit-compressed", "path": str(rel),
        "storage": "git", "bytes": len(blob),
        "file_sha256": hashlib.sha256(blob).hexdigest(),
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "enumerated_set_sha256": rec["enumerated_set_sha256"],
    }
    rows = [r for r in fbarchive.read_index()
            if not (r["curve_id"] == row["curve_id"] and
                    r["family"] == row["family"] and
                    r["seed"] == str(row["seed"]))]
    fbarchive.write_index(rows + [row])
    assert verify_doc(doc, {k: str(v) for k, v in row.items()}, rebuild=True) == []
    return row


if __name__ == "__main__":
    print(json.dumps(store_doc(build_doc())))
