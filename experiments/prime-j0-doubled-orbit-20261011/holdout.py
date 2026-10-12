#!/usr/bin/env python3
"""Freeze and replay a fresh panel for the adaptive doubled-orbit cover."""

from collections import Counter
from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = HERE.parent / "prime-j0-cycle-compression-20261011"
SOURCE_FILES = ("construct.py", "verify.py", "design_replay.py",
                "holdout.py", "verify_holdout.py")
COUNT = 4_096
SEED = 20261011112517


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


input_parent = load("doubled_input_parent",
                    HERE.parent / "prime-j0-cycle-prune-20261011/make_inputs.py")
parent = load("doubled_replay_parent",
              HERE.parent / "prime-j0-orbit-swap-20261011/replay_holdout.py")
dual = parent.dual


def digest(raw):
    return sha256(raw).hexdigest()


def write_json(path, record):
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def read_cover(path, mask):
    raw = path.read_bytes()
    magic, radix, classes, count, actual_mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, actual_mask) == \
        (b"LP21", 1024, 174_764, 67_338, mask)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    assignments = [divmod(value, 16) for (value,) in
                   struct.iter_unpack("<I", raw[20:offset])]
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    return raw, assignments, seeds


def prepare(commit):
    assert not (HERE / "holdout-inputs.json").exists()
    hashes = {}
    for name in SOURCE_FILES:
        path = f"experiments/prime-j0-doubled-orbit-20261011/{name}"
        frozen = subprocess.run(["git", "show", f"{commit}:{path}"],
                                cwd=ROOT, check=True, capture_output=True).stdout
        current = (HERE / name).read_bytes()
        assert frozen == current, name
        hashes[name] = digest(current)
    cover = (HERE / "cover-doubled.bin").read_bytes()
    check = json.loads((HERE / "check.json").read_bytes())
    assert check["status"] == "passed" and check["cover_sha256"] == digest(cover)
    previous_raw = (BASE / "holdout-inputs.json").read_bytes()
    previous = json.loads(previous_raw)
    sources = dict(previous["prior_panel_sha256"])
    sources["prime-j0-cycle-compression-20261011/holdout-inputs.json"] = \
        digest(previous_raw)
    seen = set()
    for name, expected in sorted(sources.items()):
        raw = input_parent.prior_bytes(name)
        assert digest(raw) == expected, name
        seen.update(int(value, 16) % dual.screen.ORDER for value in
                    json.loads(raw)["scalars_hex"])
    rng = random.Random(SEED)
    scalars = []
    while len(scalars) < COUNT:
        value = rng.getrandbits(256)
        reduced = value % dual.screen.ORDER
        if reduced in seen:
            continue
        seen.add(reduced)
        scalars.append(value)
    record = {"schema": 1, "seed": SEED, "count": COUNT,
              "frozen_commit": commit,
              "candidate_source_sha256": hashes,
              "cover_sha256": digest(cover),
              "prior_panel_sha256": dict(sorted(sources.items())),
              "scalar_sha256": digest(b"".join(
                  value.to_bytes(32, "big") for value in scalars)),
              "scalars_hex": [f"{value:064x}" for value in scalars]}
    write_json(HERE / "holdout-inputs.json", record)
    print(json.dumps({key: record[key] for key in
                      ("count", "frozen_commit", "cover_sha256", "scalar_sha256")},
                     sort_keys=True))


def recode(scalar, assigned, seeds, canonical, node_index):
    a, b = dual.screen.representative(scalar % dual.screen.ORDER)
    start = a, b
    assert (a + b * dual.LAMBDA_TAU - scalar) % dual.screen.ORDER == 0
    path = []
    place = 1
    reconstructed = [0, 0]
    rho_terms = double_terms = 0
    for _ in range(12):
        ra, rb = a % 1024, b % 1024
        target = node_index[canonical[ra * 1024 + rb]]
        seed_id, map_id = assigned[target]
        pair = seeds[seed_id]
        mapped = (2 * pair[0], 2 * pair[1]) if map_id == 4 \
            else dual.mapped(pair, map_id)
        choices = [(unit, digit) for unit, digit in enumerate(
            dual.screen.units(mapped))
            if digit[0] % 1024 == ra and digit[1] % 1024 == rb]
        assert choices
        unit, digit = choices[0]
        assert dual.screen.norm(digit) <= 1024 * 1024
        path.append([digit[0], digit[1], seed_id, map_id, unit])
        reconstructed[0] += place * digit[0]
        reconstructed[1] += place * digit[1]
        a, b = (a - digit[0]) // 1024, (b - digit[1]) // 1024
        place *= 1024
        rho_terms += int(seed_id != 0 and map_id == 3)
        double_terms += int(seed_id != 0 and map_id == 4)
    assert dual.screen.norm((a, b)) < dual.TERMINAL_BOUND ** 2
    reconstructed[0] += place * a
    reconstructed[1] += place * b
    assert tuple(reconstructed) == start
    return {"digits": path, "terminal": [a, b],
            "rho_terms": rho_terms, "double_terms": double_terms}


def add_counts(total, path):
    total["active_rho"] += int(path["rho_terms"] > 0)
    total["active_double"] += int(path["double_terms"] > 0)
    total["rho_terms"] += path["rho_terms"]
    total["double_terms"] += path["double_terms"]
    total["nonzero_full_window"] += sum(row[2] != 0 for row in path["digits"])
    total["max_terminal_norm"] = max(
        total["max_terminal_norm"], dual.screen.norm(path["terminal"]))


def replay():
    assert not (HERE / "holdout-paths.jsonl").exists()
    inputs_raw = (HERE / "holdout-inputs.json").read_bytes()
    inputs = json.loads(inputs_raw)
    assert inputs["candidate_source_sha256"]["holdout.py"] == \
        digest(Path(__file__).read_bytes())
    old_raw, old_assign, old_seeds = read_cover(
        BASE / "cover-cycle-compressed.bin", 15)
    new_raw, new_assign, new_seeds = read_cover(HERE / "cover-doubled.bin", 31)
    assert old_seeds == new_seeds and digest(new_raw) == inputs["cover_sha256"]
    canonical, nodes, _, _ = dual.parent.full_classes()
    node_index = {node: index for index, node in enumerate(nodes)}
    totals = {name: Counter() for name in ("parent", "doubled", "adaptive")}
    selection = Counter()
    rows = []
    for index, text in enumerate(inputs["scalars_hex"]):
        scalar = int(text, 16)
        old = recode(scalar, old_assign, old_seeds, canonical, node_index)
        new = recode(scalar, new_assign, new_seeds, canonical, node_index)
        chosen = "parent" if new["rho_terms"] and new["double_terms"] \
            else "doubled"
        for name, path in (("parent", old), ("doubled", new),
                           ("adaptive", {"parent": old, "doubled": new}[chosen])):
            add_counts(totals[name], path)
        selection[chosen] += 1
        rows.append(json.dumps({"index": index, "parent": old,
                                "doubled": new, "adaptive": chosen},
                               sort_keys=True, separators=(",", ":")))
    raw = ("\n".join(rows) + "\n").encode()
    (HERE / "holdout-paths.jsonl").write_bytes(raw)
    receipt = {"schema": 1, "status": "screened", "cases": COUNT,
               "timing_class": "path_diagnostic",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "input_sha256": digest(inputs_raw),
               "parent_cover_sha256": digest(old_raw),
               "cover_sha256": digest(new_raw),
               "certificate_sha256": digest(raw),
               "counts": {name: dict(sorted(value.items()))
                          for name, value in totals.items()},
               "adaptive_selection": dict(sorted(selection.items()))}
    write_json(HERE / "holdout-screen.json", receipt)
    print(json.dumps({"counts": receipt["counts"],
                      "adaptive_selection": receipt["adaptive_selection"]},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "replay"))
    parser.add_argument("--frozen-commit")
    arguments = parser.parse_args()
    if arguments.action == "prepare":
        assert arguments.frozen_commit
        prepare(arguments.frozen_commit)
    else:
        replay()
