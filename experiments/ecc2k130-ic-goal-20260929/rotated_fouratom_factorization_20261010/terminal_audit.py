"""Terminal evidence and resource audit for the quartic-factor experiment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    freeze = read("terminal_protocol.json")
    for name, (path, expected) in freeze["source_sha256"].items():
        assert sha(Path(path)) == expected, name
    for protocol_name in ("protocol.json", "torsion_protocol.json", "symbolic_protocol.json",
                          "symbolic_audit_protocol.json", "native_protocol.json",
                          "split_audit_protocol.json", "boolean_protocol.json"):
        protocol = read(protocol_name)
        for name, (path, expected) in protocol["source_sha256"].items():
            assert sha(Path(path)) == expected, (protocol_name, name)
    symbolic = read("symbolic_result.json")
    symbolic_audit = read("symbolic_audit_result.json")
    assert symbolic["status"] == "PASS_UNIVERSAL_ARTIN_SCHREIER_QUARTIC_FACTORIZATION"
    assert symbolic_audit["status"] == "PASS_INDEPENDENT_GF2_QUARTIC_PRODUCT_IDENTITY"
    assert symbolic_audit["symbolic_result_sha256"] == sha(HERE / "symbolic_result.json")
    assert symbolic_audit["expanded_terms"] == symbolic_audit["rebuilt_terms"] == 1452
    assert symbolic_audit["factor_terms"] == [114, 138]
    torsion = read("torsion_result.json")
    assert torsion["status"] == "PASS_TORSION_SHIFT_RESULTANT_FACTORIZATION_SCREEN"
    summary = {}
    for name in ("n41", "n131"):
        rows = torsion[name]
        summary[name] = {"cases": len(rows), "trace_zero_split": 0, "trace_one_irreducible": 0}
        for row in rows:
            degrees = row["factor_degrees_and_terms"]
            if row["trace_z"] == 0:
                assert degrees == [[4, 4, 1, 13], [4, 4, 1, 13]]
                summary[name]["trace_zero_split"] += 1
            else:
                assert degrees == [[8, 8, 1, 37]]
                summary[name]["trace_one_irreducible"] += 1
    assert summary["n41"] == {"cases": 5, "trace_zero_split": 2, "trace_one_irreducible": 3}
    assert summary["n131"] == {"cases": 7, "trace_zero_split": 3, "trace_one_irreducible": 4}
    boolean = read("boolean_result.json")
    assert boolean["status"] == "PASS_EXACT_N41_QUARTIC_BOOLEAN_SUPPORT"
    for row in boolean["cases"].values():
        assert all(factor["boolean_degree"] == 4 and factor["nonzero_coefficients"] == 236
                   for factor in row["factors"])
    assert boolean["cases"]["n41_positive"]["union_zero_count"] == 1
    assert boolean["cases"]["n41_public_target"]["union_zero_count"] == 0
    native = read("split_n131_positive.json")
    native_protocol = read("native_protocol.json")
    receipt = read("split_receipt.json")
    replay = read("split_audit_result.json")
    assert native["status"] == "COMPLETE_FACTORED_SCAN"
    assert receipt["exit_code"] == 0 and receipt["native_result_sha256"] == sha(HERE / "split_n131_positive.json")
    assert receipt["protocol_sha256"] == sha(HERE / "native_protocol.json")
    assert native["processed_product_states"] == native["total_product_states"] == 16384
    assert native["query_ns"] < native_protocol["query_cap_seconds"] * 10**9
    assert native["peak_rss_bytes"] < native_protocol["rss_cap_bytes"]
    assert replay["status"] == "PASS_INDEPENDENT_SPLIT_NATIVE_ROOT_REPLAY"
    assert replay["split_query_ns"] == native["query_ns"]
    output = {"status": "PASS_QUARTIC_FACTORIZATION_TERMINAL_AUDIT",
              "terminal_protocol_sha256": sha(HERE / "terminal_protocol.json"),
              "symbolic_terms": 1452, "factor_terms": [114, 138],
              "torsion_cases": summary,
              "n41_boolean_coefficients_per_factor": 236,
              "n131_product_states": 16384,
              "n131_split_query_ns": native["query_ns"],
              "n131_legacy_query_ns": replay["legacy_query_ns"],
              "n131_peak_rss_bytes": native["peak_rss_bytes"]}
    with (HERE / "terminal_audit.json").open("x") as result:
        json.dump(output, result, sort_keys=True, indent=2)
        result.write("\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
