"""Independent exhaustive W16 membership and receipt audit."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SUPPORT = ROOT / "n131_w16_w18_sixpair_width_gate_20261010" / "support_w16.tsv"
PRIOR = ROOT / "n131_w16_fivepair_sat_gate_20261010" / "fivepair_control_result.json"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


spec = importlib.util.spec_from_file_location("independent_bdd", HERE / "bdd.py")
bdd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bdd)


def main():
    support = {int(line.split()[0]) for line in SUPPORT.read_text().splitlines()}
    assert len(support) == 32796
    root, graph = bdd.build(support, 16)
    accepted = [mask for mask in range(1 << 16) if bdd.evaluate(root, graph, mask)]
    assert accepted == sorted(support)
    assert len(graph) == 8300
    protocol = json.loads((HERE / "protocol.json").read_text())
    control = json.loads((HERE / "control.json").read_text())
    prior = json.loads(PRIOR.read_text())
    assert control["source_sha256"] == protocol["source_sha256"]
    assert protocol["source_sha256"]["bdd"] == sha(HERE / "bdd.py")
    assert protocol["source_sha256"]["core"] == sha(HERE / "core.py")
    assert protocol["source_sha256"]["runner"] == sha(HERE / "run.py")
    assert protocol["source_sha256"]["support"] == sha(SUPPORT)
    assert control["status"] == "PASS_BDD_TRUTH_TABLE_AND_FULL_XCNF_CONTROL"
    assert control["full_assignment_check"] == {
        "cnf_clauses": control["formula"]["cnf_clauses"],
        "xor_rows": control["formula"]["native_xor_rows"]}
    assert control["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["membership"]["auxiliary_variables"] == 10 * len(graph)
    old_form, new_form = prior["formula"], control["formula"]
    assert new_form["native_xor_rows"] == old_form["native_xor_rows"]
    assert new_form["bytes"] < old_form["bytes"]
    assert new_form["cnf_clauses"] < old_form["cnf_clauses"]
    result = {"status": "PASS_EXHAUSTIVE_65536_MASKS_AND_RECEIPT_AUDIT",
              "accepted_masks": len(accepted), "rejected_masks": (1 << 16) - len(accepted),
              "decision_nodes": len(graph),
              "baseline": {"variables": old_form["variables"],
                           "cnf_clauses": old_form["cnf_clauses"],
                           "bytes": old_form["bytes"]},
              "compact": {"variables": new_form["variables"],
                          "cnf_clauses": new_form["cnf_clauses"],
                          "bytes": new_form["bytes"]},
              "source_sha256": {"bdd": sha(HERE / "bdd.py"),
                                "protocol": sha(HERE / "protocol.json"),
                                "control": sha(HERE / "control.json")}}
    with (HERE / "audit.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "accepted": len(accepted),
                      "nodes": len(graph)}))


if __name__ == "__main__":
    main()
