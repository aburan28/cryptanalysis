#!/usr/bin/env sage -python
"""Audit the target-guided terminal process and replay any public relation."""

import hashlib
import importlib.util
import json
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n41_phi_second_link_control_20261009"
spec = importlib.util.spec_from_file_location("n41_base_audit", BASE / "audit.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

N, DIM, M = 41, 6, 12


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def replay(stdout, formula, previous, suffix):
    started = time.monotonic()
    checked = base.xcnf.verify(formula, stdout)
    values = base.xcnf.model_from_stdout(stdout, checked["variables"])
    source_check = base.verify_source_assignment(BASE / "lookup.xcnf", values)
    onb = base.field.Onb(N)
    curve = base.curves.Curve(onb)
    table = json.loads((BASE / "table.json").read_text())
    basis = table["basis_coordinate_masks"]
    target = tuple(onb.fromCoords(value) for value in previous["target_coordinates"])
    endpoint = tuple(onb.fromCoords(value) for value in previous["endpoint_coordinates"])
    codes = [sum(1 << bit for bit in range(DIM)
                 if values[2 + position * DIM + bit])
             for position in range(M)]
    if (any(code not in table["valid_codes"] for code in codes) or
            codes[:2] != previous["leaf_codes"]):
        raise ValueError("model uses an invalid or changed leaf code")
    wanted_partials = [sum(1 << bit for bit in range(N)
                           if values[2 + M * DIM + index * N + bit])
                       for index in range(M - 2)]
    if (wanted_partials[0] != previous["first_root_mask"] or
            wanted_partials[9] not in suffix["masks"]):
        raise ValueError("model violates frozen first or target-conditioned root")
    states = []
    for position, code in enumerate(codes):
        _, point = base.leaf(onb, curve, basis, code, position)
        options = (point, curve.neg(point))
        if position == 0:
            states = [point]
            continue
        matching = set()
        for running in states:
            for signed in options:
                candidate = curve.add(running, signed)
                if candidate is None or candidate[0] == onb.one():
                    continue
                if position < M - 1:
                    if base.point_phi(onb, candidate) == wanted_partials[position - 1]:
                        matching.add(candidate)
                elif candidate in (endpoint, curve.neg(endpoint)):
                    matching.add(candidate)
        if not matching:
            raise ValueError("model partial chain lacks signed curve realization")
        states = sorted(matching)
    running = states[0]
    projection = curve.mul(running, 4)
    if projection not in (target, curve.neg(target)):
        raise ValueError("model sum does not project to public target")
    return {"status": "PASS_VERIFIED_PUBLIC_RELATION",
            "leaf_codes": codes, "partial_phi_masks": wanted_partials,
            "projected_target_sign": 0 if projection == target else 1,
            "guided_xcnf_check": checked,
            "source_lookup_xcnf_check": source_check,
            "independent_replay_wall_seconds": time.monotonic() - started}


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, ready_path, result_path = (HERE / name for name in
                                              ("protocol.json", "preflight.json",
                                               "result.json"))
    protocol = json.loads(protocol_path.read_text())
    ready = json.loads(ready_path.read_text())
    result = json.loads(result_path.read_text())
    if (ready["status"] != "PASS_COMPLETE_SUFFIX_AND_XCNF" or
            ready["source_sha256"]["protocol"] != sha(protocol_path) or
            result["source_sha256"]["protocol"] != sha(protocol_path) or
            result["source_sha256"]["preflight"] != sha(ready_path) or
            result["status"] == "RUNNING" or
            result["target_count"] != 1 or result["batch"] is not False):
        raise ValueError("terminal one-target receipts incomplete")
    process_path = HERE / "solver.process.json"
    process = json.loads(process_path.read_text())
    try:
        live = psutil.Process(process["pid"])
    except psutil.NoSuchProcess:
        live = None
    if (live is not None and abs(live.create_time() - process["create_time_epoch"]) < .05
            and live.is_running() and live.status() != psutil.STATUS_ZOMBIE):
        raise ValueError("target-guided solver is still live")
    formula = HERE / "guided.xcnf"
    stdout = HERE / "solver.stdout.txt"
    for key, path in (("formula", formula), ("stdout", stdout),
                      ("stderr", HERE / "solver.stderr.txt"),
                      ("process", process_path)):
        if result["source_sha256"][key] != sha(path):
            raise ValueError(f"terminal {key} hash changed")
    if result["solver_stage_wall_seconds"] > protocol["wall_cap_seconds"] + 15:
        raise ValueError("target-guided solver exceeded cap")
    suffix = json.loads((HERE / "suffix_masks.json").read_text())
    previous = json.loads((BASE / "protocol.json").read_text())
    relation = (replay(stdout, formula, previous, suffix)
                if result["status"] == "SAT_MODEL_PENDING_REPLAY" else None)
    status = "PASS_VERIFIED_RELATION" if relation else "PASS_TERMINAL_NO_MODEL"
    receipt = {
        "kind": "n41_phi_target_conditioned_suffix2_terminal_audit",
        "status": status, "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "target_count": 1, "solver_status": result["status"],
        "model_lines": result["model_lines"],
        "verified_relations": 1 if relation else 0,
        "relation": relation,
        "source_sha256": {"protocol": sha(protocol_path),
                          "preflight": sha(ready_path),
                          "result": sha(result_path),
                          "auditor": sha(Path(__file__))},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status,
                      "verified_relations": receipt["verified_relations"]}))


if __name__ == "__main__":
    main()
