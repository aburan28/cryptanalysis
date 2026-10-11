"""Bind the exact-rank witness to the audited source census."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SOURCE = BASE / "n41_seed_bin_quadratic_filter_20261009"
ORBITS = SOURCE / "x_orbits.bin"
PRODUCTION = SOURCE / "production.json"
SIGN = BASE / "n41_two_pair_sign_orbit_x_support_20261009/run.py"
CENSUS = BASE / "n41_two_free_pair_occupancy_20261009/audit.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    protocol_path = HERE / "protocol.json"
    protocol = load(protocol_path)
    result = load(HERE / "result.json")
    audit_protocol_path = HERE / "audit_protocol.json"
    audit_protocol = load(audit_protocol_path)
    audit = load(HERE / "audit.json")
    production = load(PRODUCTION)
    census = load(CENSUS)
    assert protocol["status"] == "FROZEN_BEFORE_RANK"
    assert protocol["source_sha256"] == {"rank": sha(HERE / "rank.py"),
                                          "orbits": sha(ORBITS),
                                          "production": sha(PRODUCTION)}
    assert production["status"] == "EXACT_X_ORBITS_WRITTEN"
    assert production["x_orbits_sha256"] == sha(ORBITS)
    assert production["counts"]["accepted_orbits"] == protocol["orbit_rows"]
    assert census["status"] == "PASS_FULL_EXACT_RECOUNT_AND_GROUP_REPLAY"
    assert result["status"] == "FULL_QUADRATIC_EVALUATION_RANK"
    assert result["rank"] == result["feature_count"] == protocol["feature_count"] == 1379
    assert result["independent_witness_rows"] == 1379
    assert result["rows_examined"] == 1383
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["witnesses_sha256"] == sha(HERE / "witnesses.json")
    assert audit_protocol["source_sha256"] == {
        "audit": sha(HERE / "audit.py"), "rank_source": sha(HERE / "rank.py"),
        "rank_protocol": sha(protocol_path), "rank_result": sha(HERE / "result.json"),
        "witnesses": sha(HERE / "witnesses.json"), "orbits": sha(ORBITS),
        "sign_source": sha(SIGN), "independent_sage_census": sha(CENSUS)}
    assert audit["status"] == "PASS_FULL_QUADRATIC_RANK_AND_GROUP_WITNESS_REPLAY"
    assert audit["rank"] == audit["feature_count"] == audit["witness_rows_replayed"] == 1379
    assert audit["audit_protocol_sha256"] == sha(audit_protocol_path)
    assert audit["witnesses_sha256"] == sha(HERE / "witnesses.json")
    output = {"status": "PASS_EXACT_FULL_RANK_AND_SOURCE_REPLAY",
              "curve_id": protocol["curve_id"], "candidate_id": None,
              "feature_count": 1379, "independent_witness_rows": 1379,
              "rows_examined": 1383, "support_orbits": protocol["orbit_rows"],
              "distinct_witness_seed_bins": audit["distinct_seed_bins_in_witness"],
              "source_sha256": protocol["source_sha256"],
              "result_sha256": sha(HERE / "result.json"),
              "audit_sha256": sha(HERE / "audit.json")}
    terminal = HERE / "terminal_audit.json"
    if terminal.exists():
        assert load(terminal) == output
    else:
        with terminal.open("x") as stream:
            json.dump(output, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(output["status"])


if __name__ == "__main__":
    main()
