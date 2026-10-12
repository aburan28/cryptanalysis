#!/usr/bin/env python3
"""Check Q1514 input identity, width lift, binary identity, and raw runs."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1513 = PARENT / "q20261012_fixed_pair_s3_handoff"
Q1459 = PARENT / "q20261011_wdsat_width_lift"
sys.path.insert(0, str(Q1459))
from prepare import evaluate, parse_model, transform, true  # noqa: E402
sys.path.insert(0, str(Q1513))
from run import build, pin_bits, verify  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    prepared = json.loads((HERE / "prepare_receipt.json").read_text())
    custom = json.loads((HERE / "build_direct_receipt.json").read_text())
    prior = json.loads((PARENT / "q20261011_wdsat_phase_restart/build_receipt.json").read_text())
    assert protocol["proposal_id"] == prepared["proposal_id"] == custom["proposal_id"] == "Q1514"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert custom["prior_binary_sha256"] == prior["binary_sha256"]
    assert sha(Path(custom["binary_path"]).read_bytes()) == custom["binary_sha256"]
    assert custom["branch_prefix_variable_ids"] == [x for pair in zip(range(2, 85), range(18174, 18257)) for x in pair]
    assert sha((Q1459 / "prepare.py").read_bytes()) == prepared["width_lift_source_sha256"]
    for label, cell in prepared["cells"].items():
        source = (Q1513 / f"{label}.xcnf").read_bytes()
        derived = (HERE / f"{label}.width4.xcnf").read_bytes()
        assert sha(source) == cell["source_sha256"]
        assert sha(derived) == cell["derived_sha256"]
        assert sha((Q1513 / f"{label}.json").read_bytes()) == cell["source_receipt_sha256"]
        regenerated, rules, stats = transform(source)
        assert regenerated == derived
        assert all(cell[key] == json.loads(json.dumps(value))
                   for key, value in stats.items())
        if cell["lifted_witness_replay"]:
            model = parse_model(Q1513 / f"{label}.stdout.txt", stats["original_variables"])
            original = evaluate(source, model)
            for auxiliary, prefix in rules:
                model[auxiliary] = not any(true(lit, model) for lit in prefix)
            lifted = evaluate(derived, model)
            assert cell["lifted_witness_replay"] == {"original": original, "derived": lifted}
    cells = [
        ("n53_known_pair_pinned", "selector_pair_mids"),
        ("n53_known_pair_pinned", "selector_leaf_interleave"),
        ("n83_planted_pinned", "selector_pair_mids"),
        ("n83_planted_pinned", "selector_leaf_interleave"),
        ("n83_planted_pinned", "selector_mid_interleave"),
        ("n83_planted_pinned", "direct_raw_interleave"),
        ("n83_ordinary_selected", "direct_raw_interleave"),
        ("n83_ordinary_holdout", "direct_raw_interleave"),
    ]
    summary = []
    for label, order in cells:
        stem = f"{label}.{order}"
        receipt = json.loads((HERE / f"{stem}.json").read_text())
        out = (HERE / f"{stem}.stdout.txt").read_bytes()
        err = (HERE / f"{stem}.stderr.txt").read_bytes()
        assert sha(out) == receipt["stdout_sha256"]
        assert sha(err) == receipt["stderr_sha256"]
        assert receipt["source_sha256"] == prepared["cells"][label]["source_sha256"]
        assert receipt["derived_sha256"] == prepared["cells"][label]["derived_sha256"]
        assert receipt["binary_sha256"] == (custom["binary_sha256"] if order == "direct_raw_interleave" else prior["binary_sha256"])
        error_text = err.decode(errors="replace")
        checkpoints = [int(x) for x in re.findall(r"^Q1464_BRANCH (\d+)$", error_text, re.M)]
        assert checkpoints == receipt["branch_checkpoints"]
        assert checkpoints == [1 << i for i in range(len(checkpoints))]
        assert receipt["search_started"] == ("Q1458_SEARCH_START" in error_text)
        if receipt["status"] == "SAT_VERIFIED":
            bits = [line.strip() for line in out.decode().splitlines()
                    if len(line.strip()) == prepared["cells"][label]["derived_variables"]
                    and set(line.strip()) <= {"0", "1"}]
            assert len(bits) == 1
            model = {i + 1: char == "1" for i, char in enumerate(bits[0])}
            original_count = prepared["cells"][label]["original_variables"]
            original_model = {i: model[i] for i in range(1, original_count + 1)}
            formula, raw, leaves, onb = build(json.loads((Q1513 / f"{label}.json").read_text())["n"],
                                              json.loads((Q1513 / f"{label}.json").read_text())["complement_x_coords"])
            prior_receipt = json.loads((Q1513 / f"{label}.json").read_text())
            for vector, value in zip(raw, prior_receipt["pin_raw"]):
                pin_bits(formula, vector, value)
            for vector, value in zip(leaves, prior_receipt["pin_projected"]):
                pin_bits(formula, vector, value)
            replay = {"derived_xcnf": evaluate((HERE / f"{label}.width4.xcnf").read_bytes(), model),
                      "source_xcnf": evaluate((Q1513 / f"{label}.xcnf").read_bytes(), original_model),
                      "curve": verify(formula, raw, leaves, onb, prior_receipt["complement_x_coords"], original_model)}
            assert replay == receipt["model_replay"]
        else:
            assert receipt["model_replay"] is None
            assert receipt["status"] in ("WALL_TIMEOUT_SEARCH_STARTED", "BRANCH_CAP_SEARCH_STARTED")
        summary.append({"label": label, "order": order, "status": receipt["status"],
                        "branches_checkpoint": checkpoints[-1] if checkpoints else 0})
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
