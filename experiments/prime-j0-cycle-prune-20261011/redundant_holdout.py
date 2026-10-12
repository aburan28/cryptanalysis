#!/usr/bin/env python3
"""Freeze, replay, and independently check a fresh redundant-cover panel."""

from collections import Counter
from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import random
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


input_parent = load("redundant_input_parent", HERE / "make_inputs.py")
replay_parent = load("redundant_replay_parent", HERE / "replay_holdout.py")
verify_parent = load("redundant_verify_parent", HERE / "verify_holdout.py")
reference = verify_parent.parent.reference
COUNT = 4096
SEED = 20261011095817
SOURCE_NAMES = ("augment_redundant.py", "verify_redundant.py",
                "redundant_holdout.py")
BASE = HERE / "cover-cycle-refined.bin"
NEW = HERE / "cover-cycle-redundant.bin"


def digest(raw):
    return sha256(raw).hexdigest()


def write_json(path, record):
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def prepare(commit):
    output = HERE / "redundant-inputs.json"
    assert not output.exists()
    source_hashes = {}
    for name in SOURCE_NAMES:
        path = f"experiments/prime-j0-cycle-prune-20261011/{name}"
        frozen = subprocess.run(["git", "show", f"{commit}:{path}"],
                                cwd=ROOT, check=True, capture_output=True).stdout
        current = (HERE / name).read_bytes()
        assert frozen == current, name
        source_hashes[name] = digest(current)
    cover = NEW.read_bytes()
    check = json.loads((HERE / "redundant-check.json").read_bytes())
    assert check["status"] == "passed" and digest(cover) == check["cover_sha256"]
    previous = json.loads((HERE / "holdout-inputs.json").read_bytes())
    sources = dict(previous["prior_panel_sha256"])
    sources["prime-j0-cycle-prune-20261011/holdout-inputs.json"] = \
        digest((HERE / "holdout-inputs.json").read_bytes())
    seen = set()
    for name, expected in sorted(sources.items()):
        raw = input_parent.prior_bytes(name)
        assert digest(raw) == expected
        seen.update(int(value, 16) % reference.N
                    for value in json.loads(raw)["scalars_hex"])
    rng = random.Random(SEED)
    scalars = []
    while len(scalars) < COUNT:
        value = rng.getrandbits(256)
        reduced = value % reference.N
        if reduced in seen:
            continue
        seen.add(reduced)
        scalars.append(value)
    record = {"schema": 1, "seed": SEED, "count": COUNT,
              "frozen_commit": commit,
              "candidate_source_sha256": source_hashes,
              "cover_sha256": digest(cover),
              "prior_panel_sha256": dict(sorted(sources.items())),
              "scalar_sha256": digest(b"".join(
                  value.to_bytes(32, "big") for value in scalars)),
              "scalars_hex": [f"{value:064x}" for value in scalars]}
    write_json(output, record)
    print(json.dumps({key: record[key] for key in
                      ("count", "frozen_commit", "cover_sha256", "scalar_sha256")},
                     sort_keys=True))


def replay():
    output = HERE / "redundant-paths.jsonl"
    receipt = HERE / "redundant-holdout-screen.json"
    assert not output.exists() and not receipt.exists()
    input_raw = (HERE / "redundant-inputs.json").read_bytes()
    inputs = json.loads(input_raw)
    assert inputs["candidate_source_sha256"]["redundant_holdout.py"] == \
        digest(Path(__file__).read_bytes())
    old_raw, old_assign, old_seeds = replay_parent.load_cover(BASE)
    new_raw, new_assign, new_seeds = replay_parent.load_cover(NEW)
    assert digest(new_raw) == inputs["cover_sha256"]
    canonical, nodes, _, _ = replay_parent.dual.parent.full_classes()
    node_index = {node: i for i, node in enumerate(nodes)}
    counts = {name: Counter() for name in ("refined", "redundant")}
    rows = []
    for index, value in enumerate(inputs["scalars_hex"]):
        scalar = int(value, 16)
        paths = {"refined": replay_parent.parent.recode(
                     scalar, old_assign, old_seeds, canonical, node_index),
                 "redundant": replay_parent.parent.recode(
                     scalar, new_assign, new_seeds, canonical, node_index)}
        for name, path in paths.items():
            counts[name]["active_rho"] += int(path["rho_terms"] != 0)
            counts[name]["rho_terms"] += path["rho_terms"]
            counts[name]["nonzero_full_window"] += sum(
                row[2] != 0 for row in path["digits"])
        rows.append(json.dumps({"index": index, **paths}, sort_keys=True,
                               separators=(",", ":")))
    raw = ("\n".join(rows) + "\n").encode()
    output.write_bytes(raw)
    screen = {"schema": 1, "status": "screened", "cases": COUNT,
              "source_sha256": digest(Path(__file__).read_bytes()),
              "input_sha256": digest(input_raw),
              "refined_cover_sha256": digest(old_raw),
              "redundant_cover_sha256": digest(new_raw),
              "certificate_sha256": digest(raw),
              "refined": dict(sorted(counts["refined"].items())),
              "redundant": dict(sorted(counts["redundant"].items()))}
    write_json(receipt, screen)
    print(json.dumps({"refined": screen["refined"],
                      "redundant": screen["redundant"]}, sort_keys=True))


def verify():
    input_raw = (HERE / "redundant-inputs.json").read_bytes()
    inputs = json.loads(input_raw)
    screen = json.loads((HERE / "redundant-holdout-screen.json").read_bytes())
    path_raw = (HERE / "redundant-paths.jsonl").read_bytes()
    assert digest(input_raw) == screen["input_sha256"]
    assert digest(path_raw) == screen["certificate_sha256"]
    for name, expected in inputs["candidate_source_sha256"].items():
        assert digest((HERE / name).read_bytes()) == expected
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    assert len(scalars) == screen["cases"] == COUNT
    assert digest(b"".join(value.to_bytes(32, "big") for value in scalars)) == \
        inputs["scalar_sha256"]
    reduced = {value % reference.N for value in scalars}
    assert len(reduced) == COUNT
    for name, expected in inputs["prior_panel_sha256"].items():
        raw = input_parent.prior_bytes(name)
        assert digest(raw) == expected
        assert reduced.isdisjoint(int(value, 16) % reference.N
                                  for value in json.loads(raw)["scalars_hex"])
    old_raw, old_seeds = verify_parent.read_seeds(BASE)
    new_raw, new_seeds = verify_parent.read_seeds(NEW)
    assert digest(old_raw) == screen["refined_cover_sha256"]
    assert digest(new_raw) == screen["redundant_cover_sha256"] == \
        inputs["cover_sha256"]
    reference.verify_eigenvalue()
    counts = {name: Counter() for name in ("refined", "redundant")}
    point_hash = sha256()
    rows = path_raw.splitlines()
    assert len(rows) == COUNT
    for index, (scalar, line) in enumerate(zip(scalars, rows)):
        entry = json.loads(line)
        assert entry["index"] == index
        for name, seeds in (("refined", old_seeds),
                            ("redundant", new_seeds)):
            rho, nonzero, _ = verify_parent.parent.check_path(
                entry[name], seeds, scalar)
            counts[name]["active_rho"] += int(rho != 0)
            counts[name]["rho_terms"] += rho
            counts[name]["nonzero_full_window"] += nonzero
        if index < 128:
            point = reference.group_mul(
                scalar % reference.N, (reference.GX, reference.GY))
            assert point is not None
            for coordinate in point:
                point_hash.update(coordinate.to_bytes(32, "big"))
    assert all(dict(counts[name]) == screen[name] for name in counts)
    result = {"schema": 1, "status": "passed", "cases": COUNT,
              "refined": screen["refined"],
              "redundant": screen["redundant"],
              "binary_point_samples": 128,
              "binary_point_stream_sha256": point_hash.hexdigest(),
              "certificate_sha256": digest(path_raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "reference_sha256": digest(verify_parent.PARENT.read_bytes())}
    write_json(HERE / "redundant-holdout-check.json", result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "replay", "verify"))
    parser.add_argument("--frozen-commit")
    arguments = parser.parse_args()
    if arguments.action == "prepare":
        assert arguments.frozen_commit
        prepare(arguments.frozen_commit)
    elif arguments.action == "replay":
        replay()
    else:
        verify()
