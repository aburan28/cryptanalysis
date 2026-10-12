#!/usr/bin/env sage -python
"""Independent Sage replay of a source W24/m6 SAT receipt and group relation."""

import argparse
import gzip
import hashlib
import itertools
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-263-equal-w24-workload-20261005"


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def digest_raw_or_gzip(path):
    raw = path if path.is_file() else Path(str(path) + ".gz")
    assert raw.is_file()
    hasher = hashlib.sha256()
    count = 0
    opener = gzip.open if raw.suffix == ".gz" else Path.open
    with opener(raw, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
            count += len(chunk)
    return hasher.hexdigest(), count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    if not __debug__:
        parser.error("assertions must remain enabled")
    out = args.run_dir.resolve()
    assert not (out / "sage_replay.json").exists()
    report = json.loads((out / "receipt.json").read_text())
    config = json.loads((HERE / "CONFIG.json").read_text())
    base = json.loads((PARENT / "base_selection.json").read_text())
    workload = json.loads((PARENT / "primary_workload.json").read_text())
    fixtures = json.loads((PARENT / "target_fixtures.json").read_text())
    assert report["config_sha256"] == digest(HERE / "CONFIG.json")
    xcnf_sha, xcnf_bytes = digest_raw_or_gzip(out / "system.xcnf")
    assert report["xcnf_sha256"] == xcnf_sha
    assert report["xcnf_bytes"] == xcnf_bytes
    if report.get("solver_stdout_sha256") is not None:
        assert report["solver_stdout_sha256"] == digest_raw_or_gzip(
            out / "solver.stdout.txt")[0]
        assert report["solver_stderr_sha256"] == digest(
            out / "solver.stderr.txt")
    assert report["sage_runtime_info_sha256"] == digest(out / "runtime-info.json")
    assert config["parent_base_selection_sha256"] == digest(
        PARENT / "base_selection.json")
    assert config["parent_primary_workload_sha256"] == digest(
        PARENT / "primary_workload.json")
    assert base["source"]["last_selected_mask"] == config[
        "source_last_selected_mask"]
    assert base["source"]["selected_usable_points_B"] == config[
        "source_usable_points_B"]

    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    modulus = t**131 + t**13 + t**2 + t + 1
    assert modulus.is_irreducible()
    field = GF(2**131, "t", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    r = ZZ(workload["subgroup_order"])

    def decode(value):
        return field(sum(t**j for j in range(int(value).bit_length())
                         if (int(value) >> j) & 1))

    def encode(value):
        return sum(int(bit) << j for j, bit in
                   enumerate(value.polynomial().list()))

    def point_from_words(words):
        assert len(words) == 2
        point = curve([decode(words[0]), decode(words[1])])
        assert [encode(point[0]), encode(point[1])] == words
        return point

    def words(point):
        return None if point.is_zero() else [encode(point[0]), encode(point[1])]

    def halftrace(value):
        assert value.trace() == 0
        total = field.zero()
        term = value
        for _ in range(66):
            total += term
            term = term**4
        assert total**2 + total == value
        return total

    basis = [field.gen()**j + (field.gen()**j).trace()
             for j in range(1, 25)]

    def points_for_mask(mask):
        assert 0 < mask <= config["source_last_selected_mask"]
        w = sum((basis[j] for j in range(24) if mask & (1 << j)),
                field.zero())
        assert w != 0 and w.trace() == 0 and (1/w).trace() == 0
        u = halftrace(w)
        assert u not in (0, 1)
        x = 1 + 1/u
        rhs = x + 1/(x*x)
        assert rhs.trace() == 0
        y = x*halftrace(rhs)
        first = curve([x, y])
        second = -first
        assert first != second
        assert 4*first != curve(0) and r*(4*first) == curve(0)
        return (first, second), u

    started = time.perf_counter()
    torsion = (curve(0), curve([0, 1]), curve([1, 0]), curve([1, 1]))
    assert len(set(torsion)) == 4
    assert all(4*point == curve(0) for point in torsion)
    if report["mode"] == "planted":
        masks = base["source"]["control_masks_selection_order"][:6]
        raw = []
        for mask in masks:
            options, _ = points_for_mask(mask)
            raw.append(min(options, key=lambda point: encode(point[1])))
        total = sum(raw, curve(0))
        q = 4*total
        assert report["planted_masks"] == masks
        assert report["planted_raw_points"] == [words(point) for point in raw]
        assert not total.is_zero() and not q.is_zero()
    else:
        assert report["mode"] == "ordinary"
        q = point_from_words(workload["targets"][0]["source"])
        total = None
        # The known scalar is used only here, after the SAT attempt.
        scalar_start = time.perf_counter()
        fixture_scalar = ZZ(fixtures["accepted_scalars"][0])
        generator = point_from_words(workload["generator_G"])
        assert fixture_scalar*generator == q and r*q == curve(0)
        scalar_replay_seconds = time.perf_counter() - scalar_start
    assert words(q) == report["public_q"] and r*q == curve(0)
    base_lift = ZZ(4).inverse_mod(r)*q
    fibers = tuple(base_lift + point for point in torsion)
    assert [words(point) for point in fibers] == report["raw_fibers"]
    assert all(4*point == q for point in fibers)
    if report["mode"] == "planted":
        assert fibers[report["planted_fiber_index"]] == total

    status = "NO_MODEL_REPLAYED"
    selected_points = None
    if report["model"] is not None:
        model = report["model"]
        masks = model["masks"]
        assert len(masks) == 6
        if report["mode"] == "planted":
            assert masks == report["planted_masks"]
            assert model["fiber_index"] == report["planted_fiber_index"]
        choices, us = [], []
        for mask in masks:
            options, u = points_for_mask(mask)
            choices.append(options)
            us.append(u)
        selected_fiber = fibers[model["fiber_index"]]
        assert not selected_fiber.is_zero() and selected_fiber[0] != 1
        final_u = 1/(selected_fiber[0] + 1)
        intermediate_us = [decode(value) for value in model["intermediate_us"]]
        assert len(intermediate_us) == 4 and all(u != 0 for u in intermediate_us)
        chain = [us[0]] + intermediate_us + [final_u]
        for slot in range(1, 6):
            first, second, third = chain[slot-1], us[slot], chain[slot]
            assert ((third**2+third)*(first**2+first)*(second**2+second)
                    + (first+second+third)**2) == 0
        for points in itertools.product(*choices):
            if sum(points, curve(0)) == selected_fiber:
                assert sum((4*point for point in points), curve(0)) == q
                selected_points = [words(point) for point in points]
                break
        assert selected_points is not None
        status = ("PASS_PLANTED_GROUP_REPLAY" if report["mode"] == "planted"
                  else "PASS_ORDINARY_GROUP_REPLAY")
    elapsed = time.perf_counter() - started
    result = {
        "schema": "ecc2k130-w24-natural-pdp-independent-sage-replay-v1",
        "status": status,
        "mode": report["mode"],
        "public_q": words(q),
        "model_masks": report["model"]["masks"] if report["model"] else None,
        "selected_raw_points": selected_points,
        "selected_fiber_index": (report["model"]["fiber_index"]
                                 if report["model"] else None),
        "source_usable_points_B": config["source_usable_points_B"],
        "replay_seconds": elapsed,
        "scalar_replay_seconds": (scalar_replay_seconds
                                  if report["mode"] == "ordinary" else None),
        "peak_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                           if sys.platform == "darwin" else
                           resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
        "receipt_sha256": digest(out / "receipt.json"),
        "source_sha256": digest(Path(__file__)),
        "sage_runtime_info_sha256": digest(out / "runtime-info.json"),
        "candidate_id": None,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    with (out / "sage_replay.json").open("x", encoding="utf-8") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps({"status": status, "mode": report["mode"],
                      "replay_seconds": elapsed}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
