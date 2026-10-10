#!/usr/bin/env sage -python
"""Independently replay a native six-block witness in checked Sage."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_parent_audit():
    spec = importlib.util.spec_from_file_location(
        "fixed_sum_parent_audit", PARENT / "audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent audit")
    import sys
    sys.path.insert(0, str(HERE))
    from freeze import source_paths
    protocol = json.loads((HERE / "protocol.json").read_text())
    if protocol["source_sha256"] != {
            name: sha(path) for name, path in source_paths().items()}:
        raise ValueError("frozen source mismatch")
    receipt = json.loads((HERE / "run_receipt.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    if (receipt["status"] != result["status"] or
            receipt["result_sha256"] != sha(HERE / "result.json") or
            receipt["stdout_sha256"] != sha(HERE / "join.stdout.txt") or
            receipt["stderr_sha256"] != sha(HERE / "join.stderr.txt") or
            result["peak_rss_bytes"] > protocol["rss_cap_bytes"] or
            result["total_wall_ns"] >
            (protocol["wall_cap_seconds"] + 1) * 10**9):
        raise ValueError("native terminal receipt mismatch")
    parent = load_parent_audit()
    geometry = json.loads((PARENT / "geometry.json").read_text())
    curve, elem, integer = parent.sage_curve()
    rows = parent.first_rows()
    basis = json.loads((PARENT.parent / "n41_lowpower_w8_s6/basis8.json").read_text())["basis_halftrace_by_unique_rotation"][0]
    target = curve(elem(protocol["target_q"][0]),
                   elem(protocol["target_q"][1]))
    if parent.R * target != curve(0):
        raise ValueError("public target outside subgroup")
    count = 0
    columns = []
    if result["witness"] is not None:
        if len(result["witness"]) != 6:
            raise ValueError("incorrect witness length")
        total = curve(0)
        for block, index in enumerate(result["witness"]):
            state = geometry["blocks"][block]["states"][index]
            _, _, raw_sum = parent.replay_state(
                curve, elem, integer, basis, rows,
                geometry["rotations"][block], state)
            total += 4 * raw_sum
            columns.extend(state["columns"])
            count += 1
        if total != target or len(set(columns)) != 12:
            raise ValueError("Sage relation or distinct-column replay failed")
    elif result["status"] == "FOUND_VERIFIED_RELATION":
        raise ValueError("successful status lacks witness")
    audit = {"status": "PASS_INDEPENDENT_SAGE_REPLAY",
             "native_status": result["status"], "sage_witness_pairs": count,
             "distinct_columns": len(set(columns)),
             "curve_id": protocol["curve_id"],
             "proposal_id": protocol["proposal_id"], "candidate_id": None,
             "result_sha256": sha(HERE / "result.json"),
             "protocol_sha256": sha(HERE / "protocol.json")}
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
