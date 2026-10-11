"""Check frozen source identities, panel receipts, Sage replay, and fallback controls."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OLD = BASE / "n131_w18_allseed_linear_query_20261011"
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
FIELD = BASE / "n131_w14_coupled_fouratom_inverse_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    protocol = load("protocol.json")
    expected = {
        "native_source": HERE / "native.cpp", "native_binary": HERE / "native",
        "runner": HERE / "run.py", "support": SUPPORT,
        "field_source": FIELD / "native.cpp", "field_terms": FIELD / "resultant_terms.hpp",
        "prior_protocol": OLD / "protocol.json", "prior_audit": OLD / "terminal_audit.json",
    }
    assert protocol["source_sha256"] == {name: sha(path) for name,path in expected.items()}
    audit_protocol = load("audit_protocol.json")
    audit = load("audit.json")
    assert audit["status"] == "PASS_INDEPENDENT_RANK_PRODUCT_GROUP_REPLAY"
    assert audit["audit_protocol_sha256"] == sha(HERE / "audit_protocol.json")
    assert audit_protocol["source_sha256"]["audit_source"] == sha(HERE / "audit.py")
    assert load("sage_runtime_info.json")["status"] == "verified"
    cases=[]
    for index,case in enumerate(protocol["cases"]):
        result=load(f"case_{index:03d}.json")
        receipt=load(f"case_{index:03d}.receipt.json")
        comparison=load(f"case_{index:03d}.comparison.json")
        prior=json.loads((OLD / f"case_{index:03d}_target_linear.json").read_text())
        assert receipt["status"] == result["status"] == "COMPLETE"
        assert receipt["output_sha256"] == sha(HERE / f"case_{index:03d}.json")
        assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
        assert comparison["status"] == "PASS_EXACT_HIT_MATCH"
        assert result["hits"] == prior["hits"]
        assert audit["cases"][index]["rank"] == result["joint_rank"]
        assert result["query_ns_exploratory"] < protocol["query_cap_seconds"]*10**9
        assert result["peak_rss_bytes"] < protocol["rss_cap_bytes"]
        cases.append({"name":case["name"], "rank":result["joint_rank"],
                      "consistent":result["joint_consistent"],"hits":len(result["hits"]),
                      "query_ns_exploratory":result["query_ns_exploratory"],
                      "prior_query_ns_exploratory":prior["query_ns_exploratory"]})
    fallback_protocol=load("fallback_protocol.json")
    assert fallback_protocol["source_sha256"]["native_source"] == sha(HERE / "native.cpp")
    assert fallback_protocol["source_sha256"]["native_binary"] == sha(HERE / "native")
    assert fallback_protocol["source_sha256"]["runner"] == sha(HERE / "fallback.py")
    fallback=[]
    for index,coordinate in enumerate(fallback_protocol["coordinates"]):
        new=load(f"fallback_{index:03d}_joint.json")
        old=load(f"fallback_{index:03d}_old.json")
        comparison=load(f"fallback_{index:03d}.comparison.json")
        assert comparison["status"] == "PASS_EXACT_HIT_MATCH"
        assert new["joint_rank"] < 53 and new["joint_consistent"] and new["fallback"]
        assert new["hits"] == old["hits"]
        assert new["seeds_checked"] == 262143
        assert new["status"] == old["status"] == "COMPLETE"
        assert new["query_ns_exploratory"] < fallback_protocol["query_cap_seconds"]*10**9
        assert new["peak_rss_bytes"] < fallback_protocol["rss_cap_bytes"]
        for arm in ("joint","old"):
            receipt=load(f"fallback_{index:03d}_{arm}.receipt.json")
            assert receipt["output_sha256"] == sha(HERE / f"fallback_{index:03d}_{arm}.json")
        fallback.append({"coordinate":coordinate,"rank":new["joint_rank"],
                         "query_ns_exploratory":new["query_ns_exploratory"],
                         "hits":len(new["hits"])})
    output={"status":"PASS_SOURCE_BOUND_PANEL_AND_FALLBACK",
            "protocol_sha256":sha(HERE / "protocol.json"),
            "audit_sha256":sha(HERE / "audit.json"),
            "fallback_protocol_sha256":sha(HERE / "fallback_protocol.json"),
            "cases":cases,"fallback_cases":fallback}
    with (HERE / "terminal_audit.json").open("x") as stream:
        json.dump(output,stream,sort_keys=True,indent=2)
        stream.write("\n")
    print(output["status"])


if __name__ == "__main__":
    main()
