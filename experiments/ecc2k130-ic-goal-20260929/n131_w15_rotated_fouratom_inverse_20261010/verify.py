"""Audit source freezes and the complete rotated-four-atom control panel."""

import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OLD = BASE / "n131_w14_coupled_fouratom_inverse_20261010/resultant_terms.json"
SCREEN = BASE / "n41_n131_diagonal_atom_20261010/screen.json"
HIT = BASE / "n131_w15_cross_block_seed_offset_20261010/n41_hit.json"
LIFT = BASE / "n131_w15_coupled_sixpair_20261010/control_group_lift.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def check(expected, paths):
    assert expected == {key: sha(path) for key,path in paths.items()}


def combine(limbs):
    return limbs[0] + (limbs[1] << 64) + (limbs[2] << 128)


def main():
    assert not (HERE / "terminal_audit.json").exists()
    protocol = read("protocol.json")
    check(protocol["source_sha256"], {"derive.py": HERE / "derive.py",
        "old_resultant": OLD, "sage_runtime_info": HERE / "sage_runtime_info.json"})
    resultant = read("resultant.json")
    assert resultant["protocol_sha256"] == sha(HERE / "protocol.json")
    assert resultant["status"] == "PASS_UNIVERSAL_ROTATED_FOUR_ATOM_RESULTANT"
    assert resultant["term_count"] == len(resultant["terms"]) == 266
    assert resultant["degrees"] == {key: 8 for key in ("a","b","p","q","z")}
    terms = {tuple(row) for row in resultant["terms"]}
    assert len(terms) == 266
    assert {(b,a,q,p,z) for a,b,p,q,z in terms} == terms
    specialized = Counter((a+b,p,q,z) for a,b,p,q,z in terms)
    reduced = {item for item,count in specialized.items() if count & 1}
    old = json.loads(OLD.read_text())
    assert reduced == {tuple(row) for row in old["terms_s_p_q_z"]}
    control_protocol = read("control_protocol.json")
    check(control_protocol["source_sha256"], {
        "control.py": HERE / "control.py", "resultant": HERE / "resultant.json",
        "n41_screen": SCREEN, "n41_hit": HIT, "n131_lift": LIFT,
        "sage_runtime_info": HERE / "sage_runtime_info.json"})
    control = read("control_result.json")
    assert control["protocol_sha256"] == sha(HERE / "control_protocol.json")
    assert control["status"] == "PASS_ROTATED_RESULTANT_N41_PUBLIC_ROW_AND_N131_CONTROL"
    assert control["n41"]["product_family_states_checked"] == 1024
    assert control["n41"]["positive_algebraic_product_hits"] == [control["n41"]["rotated_pair_products"]]
    assert control["n41"]["control_algebraic_product_hits"] == []
    assert control["n131"]["positive_resultant_zero"]
    header = read("header_receipt.json")
    check(header["source_sha256"], {
        "emit_header.py": HERE / "emit_header.py", "resultant.json": HERE / "resultant.json",
        "rotated_terms.hpp": HERE / "rotated_terms.hpp"})
    native_protocol = read("native_protocol.json")
    check(native_protocol["source_sha256"], {key: HERE / key for key in
          ("native.cpp", "native", "rotated_terms.hpp", "resultant.json",
           "control_result.json", "run_native.py", "prepare_native.py")})
    check(native_protocol["input_sha256"], {key: HERE / key for key in native_protocol["input_sha256"]})
    audit_protocol = read("audit_protocol.json")
    check(audit_protocol["sha256"], {key: HERE / key for key in audit_protocol["sha256"]})
    audit = read("native_audit.json")
    assert audit["status"] == "PASS_INDEPENDENT_NATIVE_ROTATED_GCD_SAGE_REPLAY"
    assert audit["protocol_sha256"] == sha(HERE / "audit_protocol.json")
    assert [(row["case"],row["algebraic_hits"]) for row in audit["cases"]] == [
        ("n41_positive",1),("n41_field_control",0),
        ("n131_positive",1),("n131_field_control",0)]
    records = []
    for row in audit["cases"]:
        label = row["case"]
        native = read(f"native_{label}.json")
        receipt = read(f"receipt_{label}.json")
        assert receipt["status"] == "PROCESS_COMPLETE" and receipt["exit_code"] == 0
        assert receipt["result_sha256"] == sha(HERE / f"native_{label}.json")
        assert receipt["protocol_sha256"] == sha(HERE / "native_protocol.json")
        assert native["status"] == "COMPLETE_ALGEBRAIC_SCAN"
        assert native["processed_product_states"] == native["total_product_states"] == row["processed_first_products"]
        assert len(native["hits"]) == row["algebraic_hits"]
        assert native["query_ns"] == row["query_ns"]
        assert native["peak_rss_bytes"] == row["peak_rss_bytes"]
        assert native["query_ns"] < 100*10**9 and native["peak_rss_bytes"] < 4294967296
        if row["algebraic_hits"]:
            assert combine(native["hits"][0]["p"]) == control[label.split("_")[0]]["rotated_pair_products"][0]
        records.append({"case": label, "status": native["status"],
                        "first_products": native["processed_product_states"],
                        "algebraic_hits": row["algebraic_hits"],
                        "query_ns": native["query_ns"], "peak_rss_bytes": native["peak_rss_bytes"]})
    terminal = {"status": "PASS_ROTATED_RESULTANT_AND_NATIVE_W15_CONTROL_PANEL",
                "candidate_id": None, "universal_resultant_terms": 266,
                "same_seed_specialization_terms": len(reduced),
                "n41_sage_product_families_checked": 1024,
                "cases": records,
                "source_sha256": {name: sha(HERE / name) for name in
                                  ("verify.py", "resultant.json", "control_result.json",
                                   "native_protocol.json", "native_audit.json")}}
    with (HERE / "terminal_audit.json").open("x") as output:
        json.dump(terminal, output, sort_keys=True, indent=2)
        output.write("\n")
    print(terminal["status"])


if __name__ == "__main__":
    main()
