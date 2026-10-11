"""Terminal audit of corrected coordinates, raw lift, and source character."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    frozen = read("terminal_protocol.json")
    for name, (path, digest) in frozen["source_sha256"].items():
        assert sha(Path(path)) == digest, name
    for name in ("protocol.json", "audit_protocol.json", "lift_protocol.json",
                 "source_trace_protocol.json"):
        protocol = read(name)
        for label, (path, digest) in protocol["source_sha256"].items():
            assert sha(Path(path)) == digest, (name, label)
    corrected = read("result.json")
    audit = read("audit_result.json")
    lift = read("lift_result.json")
    source_trace = read("source_trace_result.json")
    assert corrected["status"] == "PASS_CORRECTED_RECIPROCAL_X_PUBLIC_LIFTS"
    assert audit["status"] == "PASS_INDEPENDENT_RECIPROCAL_X_LIFT_CORRECTION"
    assert lift["status"] == "PASS_N41_PUBLIC_RELATION_CORRECTED_RAW_LIFT"
    assert source_trace["status"] == "PASS_W6_W15_TWO_DESCENT_TARGET_LIFT_GATE"
    assert audit["result_sha256"] == sha(HERE / "result.json")
    assert audit["prior_n131_public_lift_coordinate_mismatches"] == 4
    assert lift["raw_preimage_index"] == 1
    assert lift["raw_sum"] == corrected["n41"]["preimages"][1]["point"]
    assert all(block["trace_z_h"] == 0 for block in lift["four_atom_blocks"])
    for n in ("n41", "n131"):
        rows = corrected[n]["preimages"]
        assert [row["trace_z_h"] for row in rows] == [0, 0, 1, 1]
        assert all(row["factor_degrees_and_terms"] == [[4, 4, 1, 13], [4, 4, 1, 13]]
                   for row in rows[:2])
        assert all(row["factor_degrees_and_terms"] == [[8, 8, 1, 37]] for row in rows[2:])
        assert source_trace["cases"][n]["admissible_public_raw_lift_indices_by_trace"] == [0, 1]
        assert source_trace["cases"][n]["excluded_public_raw_lift_indices_by_trace"] == [2, 3]
    output = {"status": "PASS_CORRECTED_PUBLIC_LIFT_TERMINAL_AUDIT",
              "terminal_protocol_sha256": sha(HERE / "terminal_protocol.json"),
              "corrected_public_lifts_per_field": 4,
              "retained_source_character_lifts": [0, 1],
              "known_n41_relation_raw_lift": 1,
              "n131_archived_transformed_coordinate_mismatches": 4}
    with (HERE / "terminal_audit.json").open("x") as handle:
        json.dump(output, handle, sort_keys=True, indent=2)
        handle.write("\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
