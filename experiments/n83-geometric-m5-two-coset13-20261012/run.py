#!/usr/bin/env python3
"""Run orbit-complete five-summand PDP on the N83 two-coset width-13 base."""

import gzip
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODEGEN = ROOT / "ecc2k130/runner/codegen"
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
M5 = ROOT / "experiments/m5-s3-gate-20261004"
S3 = ROOT / "experiments/compact-s3-m4-20261003"
sys.path[:0] = [str(CODEGEN), str(PAIR), str(M5), str(S3)]

import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from build_m5 import canonical_projected_x, replay_model  # noqa: E402
from chain_s3 import Formula, multiplication_table, product, square_destinations  # noqa: E402
from chain_s3_multitarget import choose_target_x  # noqa: E402
from cofactor_preimages import kernel_of_cofactor  # noqa: E402
from run_gate import raw_preimage_coset, solve_limited  # noqa: E402
from run_group_add_probe import stats  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def base_x_keys(row, onb, orbit):
    path = ROOT / row["base_file"]
    assert sha(path) == row["base_sha256"]
    data = path.read_bytes()
    assert len(data) == 21 * row["K"]
    keys = [int.from_bytes(data[i:i + 21], "little")
            for i in range(0, len(data), 21)]
    assert keys == sorted(set(keys))
    points = [orbit.point_from_key(key) for key in keys]
    assert all(point is not None for point in points)
    xkeys = {canonical_projected_x(onb, point, 83) for point in points}
    assert len(xkeys) == row["K"], "canonical x must distinguish the orbits"
    return xkeys


def symbolic_xor(formula, left, right):
    if left == -1:
        return right
    if right == -1:
        return left
    if left == 1:
        return -right
    if right == 1:
        return -left
    if left == right:
        return -1
    if left == -right:
        return 1
    output = formula.new()
    formula.xor_relation((output, left, right))
    return output


def s3_link_folded(formula, left, right, output, multiplication, square_dest):
    pair = product(formula, left, right, multiplication)
    sum_lr = [symbolic_xor(formula, a, b)
              for a, b in zip(left, right)]
    cross = product(formula, sum_lr, output, multiplication)
    triple = product(formula, pair, output, multiplication)
    for source, dest in enumerate(square_dest):
        formula.xor_relation((pair[source], cross[source], triple[dest]), True)


def build_affine_formula(dimension, offset, basis, target_xs, onb):
    assert dimension == len(basis) == 13
    assert basis[:12] == [1 << i for i in range(12)]
    assert basis[12] & ((1 << 12) - 1) == 0
    n = 83
    formula = Formula()
    # A rotated basis vector can occupy several normal-basis coordinates.
    # Here its four high bits remain disjoint from the twelve coordinate
    # vectors, so each leaf coordinate is one seed literal or a constant.
    rotations = []
    for power in range(n):
        sources = [-1] * n
        for source, basis_vector in enumerate(basis):
            image = onb.toCoords(onb.frob(onb.fromCoords(basis_vector), power))
            while image:
                low = image & -image
                destination = low.bit_length() - 1
                assert sources[destination] == -1
                sources[destination] = source
                image ^= low
        fixed = onb.toCoords(onb.frob(onb.fromCoords(offset), power))
        rotations.append((sources, fixed))
    leaves = []
    seed_bits = []
    orbit_selectors = []
    for _ in range(5):
        seed = [formula.new() for _ in range(dimension)]
        selector = [formula.new() for _ in range(n)]
        leaf = [formula.new() for _ in range(n)]
        formula.clauses.append(selector[:])
        for left in range(n):
            for right in range(left + 1, n):
                formula.clauses.append([-selector[left], -selector[right]])
        for power, (sources, fixed) in enumerate(rotations):
            gate = -selector[power]
            for position, source in enumerate(sources):
                value = seed[source] if source >= 0 else -1
                if (fixed >> position) & 1:
                    value = -value
                formula.clauses.append([gate, -leaf[position], value])
                formula.clauses.append([gate, leaf[position], -value])
        leaves.append(leaf)
        seed_bits.append(seed)
        orbit_selectors.append(selector)
    intermediates = [[formula.new() for _ in range(n)] for _ in range(3)]
    target, target_selector = choose_target_x(formula, n, target_xs)
    multiplication = multiplication_table(onb)
    square_dest = square_destinations(onb)
    for left, right, output in (
        (leaves[0], leaves[1], intermediates[0]),
        (leaves[2], leaves[3], intermediates[1]),
        (intermediates[0], intermediates[1], intermediates[2]),
        (intermediates[2], leaves[4], target),
    ):
        s3_link_folded(formula, left, right, output,
                       multiplication, square_dest)
    formula.orbit_seed_bits = seed_bits
    formula.orbit_selectors = orbit_selectors
    formula.intermediates = intermediates
    formula.target_x_bits = target
    return formula, leaves, target_selector


def in_rotated_affine_seed(onb, x, dimension, offset, basis):
    assert dimension == 13 and basis[:12] == [1 << i for i in range(12)]
    low_mask = (1 << 12) - 1
    delta = basis[12]
    assert delta & low_mask == 0
    element = onb.fromCoords(x)
    for power in range(83):
        seed = onb.toCoords(onb.frob(element, power)) ^ offset
        high = seed & ~low_mask
        if high == 0 or high == delta:
            return True
    return False


def archive_formula(path):
    raw = path.read_bytes()
    compressed = Path(str(path) + ".gz")
    with gzip.open(compressed, "xb") as stream:
        stream.write(raw)
    path.unlink()
    return {"xcnf_gzip": compressed.name,
            "xcnf_gzip_sha256": sha(compressed),
            "xcnf_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "xcnf_raw_bytes": len(raw)}


def one_base(protocol, row, onb, curve, order, public, kernel, orbit):
    dimension = row["dimension"]
    output = HERE / f"width{dimension}_ordinary.json"
    assert not output.exists(), "frozen run already exists"
    base_keys = base_x_keys(row, onb, orbit)
    limits = protocol["limits"]
    binary = Path(protocol["solver"]["path"])
    assert sha(binary) == protocol["solver"]["sha256"]
    started = time.perf_counter_ns()
    preimage_started = time.perf_counter_ns()
    raw_targets, target_xs = raw_preimage_coset(
        onb, curve, order, 4, public, kernel)
    preimage_ns = time.perf_counter_ns() - preimage_started
    formula_started = time.perf_counter_ns()
    formula, leaves, selector = build_affine_formula(
        dimension, row["offset_onb_coordinates"],
        row["basis_onb_coordinates"], target_xs, onb)
    formula_ns = time.perf_counter_ns() - formula_started
    shape = stats(formula)
    attempts = []
    relation = None
    deadline = started + int(limits["wall_seconds_per_base"] * 1e9)
    for index in range(limits["max_models_per_base"]):
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            break
        xcnf = HERE / f"width{dimension}.attempt{index}.xcnf"
        assert not xcnf.exists() and not Path(str(xcnf) + ".gz").exists()
        write_started = time.perf_counter_ns()
        formula.write(xcnf)
        write_ns = time.perf_counter_ns() - write_started
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            native = {"status": "no_solver_budget", "return_code": None,
                      "wall_seconds": 0.0, "conflicts_reported": None,
                      "observed_peak_solver_rss_bytes": None,
                      "rss_sample_interval_ms": 50, "command": None,
                      "stdout": "", "stderr": "", "model": None}
        else:
            native = solve_limited(
                xcnf, binary, remaining,
                protocol["solver"]["max_conflicts"],
                limits["sampled_solver_rss_stop_bytes"])
        check_started = time.perf_counter_ns()
        replay = None
        if native["model"] is not None:
            model = dict(native["model"])
            model[1] = True
            replay = replay_model(
                onb, curve, order, 4, 83, base_keys, public, raw_targets,
                leaves, selector, model)
            if "raw_leaf_x" in replay and any(
                not in_rotated_affine_seed(
                    onb, x, dimension, row["offset_onb_coordinates"],
                    row["basis_onb_coordinates"])
                for x in replay["raw_leaf_x"]
            ):
                replay = {"status": "outside_rotated_affine_x_subspace",
                          "raw_leaf_x": replay["raw_leaf_x"]}
            if replay["status"] == "verified_five_point_relation":
                relation = replay
            elif index + 1 < limits["max_models_per_base"]:
                block = [-bit if model.get(bit, False) else bit
                         for leaf in leaves for bit in leaf if bit > 1]
                block += [-bit if model.get(bit, False) else bit
                          for bit in selector]
                formula.clauses.append(block)
        check_ns = time.perf_counter_ns() - check_started
        attempt = {
            "index": index, "status": native["status"],
            "return_code": native["return_code"],
            "solver_command": native["command"],
            "solver_wall_seconds": native["wall_seconds"],
            "conflicts_reported": native["conflicts_reported"],
            "observed_peak_solver_rss_bytes": native[
                "observed_peak_solver_rss_bytes"],
            "rss_sample_interval_ms": native["rss_sample_interval_ms"],
            "formula_write_ns": write_ns,
            "relation_check_ns": check_ns,
            "model_present": native["model"] is not None,
            "formula_path": xcnf,
            "stdout": native["stdout"],
            "stderr": native["stderr"],
            "replay": replay,
        }
        attempts.append(attempt)
        if relation is not None or native["model"] is None:
            break
    online_ns = time.perf_counter_ns() - started
    archived_attempts = []
    for attempt in attempts:
        index = attempt["index"]
        stdout = HERE / f"width{dimension}.attempt{index}.stdout.txt"
        stderr = HERE / f"width{dimension}.attempt{index}.stderr.txt"
        stdout.write_text(attempt["stdout"])
        stderr.write_text(attempt["stderr"])
        archived_attempts.append({
            key: value for key, value in attempt.items()
            if key not in ("formula_path", "stdout", "stderr")
        } | {
            "stdout_file": stdout.name, "stdout_sha256": sha(stdout),
            "stderr_file": stderr.name, "stderr_sha256": sha(stderr),
            **archive_formula(attempt["formula_path"]),
        })
    phases = {"target_preimages": preimage_ns,
              "formula_build": formula_ns,
              "formula_write": sum(a["formula_write_ns"] for a in attempts),
              "solver": sum(int(a["solver_wall_seconds"] * 1e9)
                            for a in attempts),
              "relation_check": sum(a["relation_check_ns"] for a in attempts)}
    phases["target_dependent_overhead"] = max(0, online_ns - sum(phases.values()))
    if relation is not None:
        status = "verified_relation"
    elif attempts and attempts[-1]["status"] == "unsat":
        status = "unsat"
    elif attempts and attempts[-1]["model_present"]:
        status = "invalid_models_cap"
    else:
        status = "bounded_unknown"
    record = {
        "kind": "n83_two_coset_orbit_complete_five_summand_stage",
        "status": status,
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "dimension": dimension,
        "offset_onb_coordinates": row["offset_onb_coordinates"],
        "basis_onb_coordinates": row["basis_onb_coordinates"],
        "K": row["K"], "B": row["B"],
        "base_sha256": row["base_sha256"],
        "public_point_onb_raw": protocol["workload"]["public_point_onb_raw"],
        "raw_target_preimage_count": len(raw_targets),
        "raw_target_x_sha256": hashlib.sha256(b"".join(
            x.to_bytes(11, "little") for x in target_xs)).hexdigest(),
        "formula_shape": shape,
        "attempts": archived_attempts,
        "verified_relation": relation,
        "online_pdp_wall_ns_exploratory": online_ns,
        "online_pdp_phase_ns": phases,
        "timing_tier": protocol["timing_tier"],
        "peak_runner_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runner_sha256": sha(Path(__file__)),
    }
    save(output, record)
    print(json.dumps({"dimension": dimension, "status": status,
                      "attempts": [a["status"] for a in attempts],
                      "online_pdp_seconds": online_ns / 1e9}), flush=True)


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["proposal_id"] == "Q2026101290"
    assert protocol["candidate_id"] is None
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    basis_path = ROOT / protocol["basis_manifest_file"]
    assert sha(basis_path) == protocol["basis_manifest_sha256"]
    union_path = ROOT / protocol["union_receipt_file"]
    assert sha(union_path) == protocol["union_receipt_sha256"]
    identity_path = PAIR / "runs/n83_knownlog_orbit_base_k48194.json"
    assert sha(identity_path) == protocol["curve_identity_sha256"]
    identity = json.loads(identity_path.read_text())
    model = identity["curve_identity_record"]["curve"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    order = model["subgroup_order"]
    public = tuple(protocol["workload"]["public_point_onb_raw"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    assert sha(Path(protocol["solver"]["path"])) == protocol["solver"]["sha256"]
    setup_started = time.perf_counter_ns()
    kernel, _, _ = kernel_of_cofactor(curve, onb, order, 4, 141783)
    setup_ns = time.perf_counter_ns() - setup_started
    assert len(kernel) == 4
    for dimension in protocol["run_order"]:
        row = next(row for row in protocol["base_rows"]
                   if row["dimension"] == dimension)
        one_base(protocol, row, onb, curve, order, public, kernel, orbit)
    save(HERE / "run_summary.json", {
        "kind": "n83_two_coset_five_summand_stage_summary",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "target_independent_kernel_setup_ns": setup_ns,
        "run_order": protocol["run_order"],
        "result_sha256": {str(d): sha(HERE / f"width{d}_ordinary.json")
                          for d in protocol["run_order"]},
    })


if __name__ == "__main__":
    main()
