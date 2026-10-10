#!/usr/bin/env python3
"""Sound fixed-sum partial-output gate with structurally chosen free bits."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PARTIAL_SOURCE = GOAL / "n131_w18_partial_output_linear_gate.py"
PAIR_SOURCE = GOAL.parent / "koblitz-polynomial-w-pair-20260925/pair_oracle.py"
CIRCUIT_SOURCE = GOAL.parent / "koblitz-s5-invariant-20260924/circuit_sat.py"
REPLAY_SOURCE = Path("/Volumes/SSD990/crypto/research/sat_factor_base_review_20260908/autolab_orbit_extract_20260924/independent_replay.py")
PROBE = GOAL / "n131_w18_full_width_pair_oracle/probe.json"
PROBE_AUDIT = GOAL / "n131_w18_full_width_pair_oracle/independent_sage_replay.json"
CONTROLS = GOAL / "n131_w18_partial_output_linear_gate.json"
sys.path.insert(0, str(GOAL))
from n131_w18_partial_output_linear_gate import Field, half_trace  # noqa: E402

N = 131
K_VALUES = (40, 48)
PROPOSAL_ID = "Q20261009192000"
TIME_CAP_NS = 300_000_000_000
RSS_CAP_BYTES = 4 * 1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_paths():
    return [HERE / "run.py", HERE / "freeze.py", HERE / "audit.py",
            HERE / "sage_runtime_info.json", PARTIAL_SOURCE, PAIR_SOURCE,
            CIRCUIT_SOURCE, REPLAY_SOURCE, PROBE, PROBE_AUDIT, CONTROLS]


def insert_high(pivots, value):
    while value:
        bit = value.bit_length() - 1
        if bit not in pivots:
            pivots[bit] = value
            return True
        value ^= pivots[bit]
    return False


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def positive_groups():
    source = json.loads(PROBE.read_text())
    if source["status"] != "PASS" or source["verified_queries"] != 128:
        raise ValueError("frozen pair source changed")
    groups = {}
    for query in source["queries"]:
        if query.get("z") is None:
            continue
        for witness in query["matching_witnesses"]:
            left, right = witness["w_masks"]
            s = left ^ right
            if s == 0 or s >= 1 << 18:
                raise ValueError("invalid saved seed sum")
            groups.setdefault(s, set()).add(query["z"])
    if len(groups) != 32:
        raise ValueError("saved positive seed-sum count changed")
    return {s: sorted(values) for s, values in sorted(groups.items())}


def field_seed(mask):
    return sum(((mask >> bit) & 1) << (bit + 1) for bit in range(18))


def image_basis(field, s):
    pivots = {}
    for bit in range(1, 19):
        w = 1 << bit
        insert_high(pivots, field.mul(w, w) ^ field.mul(s, w))
    if len(pivots) != 17:
        raise ValueError("fixed-sum product image rank changed")
    return list(pivots.values())


def bit_blocks(field, image):
    blocks = []
    for bit in range(N):
        e = 1 << bit
        square = field.mul(e, e)
        blocks.append([square] + [field.mul(square ^ e, value) for value in image])
    return blocks


def base_from_bits(blocks, bits):
    pivots = {}
    insert_high(pivots, 1)  # Free raw-lift parity epsilon.
    for bit in bits:
        for value in blocks[bit]:
            insert_high(pivots, value)
    return pivots


def greedy_bits(blocks):
    chosen = []
    pivots = base_from_bits(blocks, ())
    ranks = []
    for _ in range(max(K_VALUES)):
        best = None
        for bit in range(N):
            if bit in chosen:
                continue
            trial = pivots.copy()
            for value in blocks[bit]:
                insert_high(trial, value)
            option = (len(trial), bit, trial)
            if best is None or option[:2] < best[:2]:
                best = option
        rank, bit, pivots = best
        chosen.append(bit)
        ranks.append(rank)
    return chosen, ranks


def gate(field, h_square, image, bits, base, z):
    unknown_mask = sum(1 << bit for bit in bits)
    fixed = z & ~unknown_mask
    fixed_square = field.mul(fixed, fixed)
    multiplier = fixed_square ^ fixed
    pivots = base.copy()
    for value in image:
        insert_high(pivots, field.mul(multiplier, value))
    residual = fixed_square ^ h_square
    while residual:
        bit = residual.bit_length() - 1
        if bit not in pivots:
            return False, len(pivots)
        residual ^= pivots[bit]
    return True, len(pivots)


def main():
    result_path = HERE / "result.json"
    if result_path.exists():
        raise FileExistsError("preserve first frozen result")
    protocol = json.loads((HERE / "protocol.json").read_text())
    if protocol["source_sha256"] != {str(path): sha(path) for path in source_paths()}:
        raise ValueError("frozen source or input changed")
    setup_start = time.monotonic_ns()
    groups = positive_groups()
    control_source = json.loads(CONTROLS.read_text())
    controls = control_source["uniform_field_controls"]
    if len(controls) != 64:
        raise ValueError("control panel changed")
    field = Field(N, [0, 1, 2, 13])
    half_squares = [field.mul(h, h) for h in
                    (half_trace(field, 1 << bit) for bit in range(1, 19))]
    setup_ns = time.monotonic_ns() - setup_start
    stage_start = time.monotonic_ns()
    image_ns = greedy_ns = gate_ns = 0
    rows = []
    for mask, positives in groups.items():
        start = time.monotonic_ns()
        seed_sum = field_seed(mask)
        image = image_basis(field, seed_sum)
        h_square = 0
        for bit in range(18):
            if (mask >> bit) & 1:
                h_square ^= half_squares[bit]
        blocks = bit_blocks(field, image)
        image_ns += time.monotonic_ns() - start
        start = time.monotonic_ns()
        selected, selected_ranks = greedy_bits(blocks)
        greedy_ns += time.monotonic_ns() - start
        policies = {}
        start = time.monotonic_ns()
        for policy in ("low", "greedy"):
            for k in K_VALUES:
                bits = list(range(k)) if policy == "low" else selected[:k]
                base = base_from_bits(blocks, bits)
                positive = [gate(field, h_square, image, bits, base, z)[0]
                            for z in positives]
                controls_pass = [gate(field, h_square, image, bits, base, z)[0]
                                 for z in controls]
                if not all(positive):
                    raise ValueError("sound gate rejected a saved positive")
                policies[f"{policy}_{k}"] = {
                    "base_rank": len(base), "positive_pass": positive,
                    "control_pass": controls_pass,
                    "control_pass_count": sum(controls_pass)}
        gate_ns += time.monotonic_ns() - start
        rows.append({"seed_sum_mask": mask, "positive_z": positives,
                     "image_rank": len(image), "greedy_bits_48": selected,
                     "greedy_base_ranks": selected_ranks, "policies": policies})
        if time.monotonic_ns() - stage_start > TIME_CAP_NS:
            raise TimeoutError("structural gate exceeded frozen time cap")
        if rss_bytes() > RSS_CAP_BYTES:
            raise MemoryError("structural gate exceeded frozen RSS cap")
    total_ns = time.monotonic_ns() - stage_start
    totals = {key: sum(row["policies"][key]["control_pass_count"] for row in rows)
              for key in ("low_40", "greedy_40", "low_48", "greedy_48")}
    result = {"status": "COMPLETE_FIXED_SUM_PARTIAL_RANK_PANEL",
              "proposal_id": PROPOSAL_ID, "candidate_id": None, "run_id": None,
              "curve_id": "EC1N131Ckb1h136f03e58c98", "target_count": 0,
              "seed_sum_count": len(rows), "control_count_per_sum": len(controls),
              "setup_ns": setup_ns, "image_build_ns": image_ns,
              "greedy_selection_ns": greedy_ns, "gate_evaluation_ns": gate_ns,
              "interval_overhead_ns": total_ns - image_ns - greedy_ns - gate_ns,
              "charged_structural_ns": total_ns, "peak_rss_bytes": rss_bytes(),
              "totals": totals, "rows": rows,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": protocol["source_sha256"]}
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "seed_sum_count": len(rows),
                      "control_count_per_sum": len(controls), "totals": totals,
                      "charged_structural_ns": total_ns,
                      "peak_rss_bytes": result["peak_rss_bytes"]}, sort_keys=True))


if __name__ == "__main__":
    main()
