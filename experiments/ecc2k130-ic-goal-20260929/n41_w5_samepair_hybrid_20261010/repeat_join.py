#!/usr/bin/env python3
"""Frozen same-target join repeats with row-order permutations only."""

import argparse
import hashlib
import json
import random
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JOIN = ROOT / "n41_w5_ten_native_join_20261010" / "join"
SEEDS = (202610102141, 202610102142, 202610102143, 202610102144)
PROBES = 2000000
SECONDS = 60


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def split_input():
    rows = (HERE / "input.txt").read_text().splitlines()
    header = rows[:5]
    blocks = []
    at = 5
    for _ in range(10):
        assert rows[at] == "34"
        blocks.append(rows[at+1:at+35])
        at += 35
    assert at == len(rows)
    return header, blocks


def freeze():
    header, blocks = split_input()
    inputs = {}
    for index, seed in enumerate(SEEDS, 1):
        folder = HERE / "repeats" / f"R{index}"
        folder.mkdir(parents=True, exist_ok=False)
        lines = list(header)
        for slot, block in enumerate(blocks):
            values = list(block)
            random.Random(seed + slot).shuffle(values)
            assert sorted(values) == sorted(block)
            lines.extend(["34", *values])
        path = folder / "input.txt"
        path.write_text("\n".join(lines) + "\n")
        inputs[f"R{index}"] = sha(path)
    record = {"status": "FROZEN_BEFORE_SAME_TARGET_REPEATS",
              "candidate_id": None,
              "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
              "public_target_q": [1458168294740, 1672312028033],
              "actual_factor_base_points_B": 170,
              "folded_columns_K": 14,
              "target_count": 1, "seeds": list(SEEDS),
              "probe_cap_per_repeat": PROBES,
              "wall_cap_seconds_per_repeat": SECONDS,
              "rss_cap_bytes": 4 * 1024**3,
              "source_sha256": {"script": sha(Path(__file__)),
                                "canonical_input": sha(HERE / "input.txt"),
                                "native_join": sha(JOIN)},
              "repeat_input_sha256": inputs}
    save(HERE / "repeat_protocol.json", record)
    print(json.dumps({"status": record["status"], "repeats": len(inputs)}))


def run():
    record = json.loads((HERE / "repeat_protocol.json").read_text())
    assert record["status"] == "FROZEN_BEFORE_SAME_TARGET_REPEATS"
    assert record["source_sha256"] == {
        "script": sha(Path(__file__)), "canonical_input": sha(HERE / "input.txt"),
        "native_join": sha(JOIN)}
    results = []
    for index, seed in enumerate(SEEDS, 1):
        folder = HERE / "repeats" / f"R{index}"
        assert record["repeat_input_sha256"][f"R{index}"] == sha(folder / "input.txt")
        command = [str(JOIN), str(folder / "input.txt"),
                   str(folder / "hits.jsonl"), str(folder / "result.json"),
                   str(PROBES), str(SECONDS)]
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=SECONDS + 10, check=False)
        (folder / "stdout.txt").write_text(completed.stdout)
        (folder / "stderr.txt").write_text(completed.stderr)
        result = json.loads((folder / "result.json").read_text())
        if completed.returncode != 0 or result["status"] not in (
                "FOUND_PENDING_SAGE_REPLAY", "CENSORED_PROBES", "CENSORED_TIME"):
            raise RuntimeError(f"repeat R{index} failed: {completed.stderr}")
        row = {"repeat": index, "seed": seed,
               "status": result["status"],
               "right_distinct_probes": result["right_distinct_probes"],
               "group_hits": result["group_hits"],
               "column_rejects": result["column_rejects"],
               "wall_ns": result["wall_ns"],
               "input_sha256": sha(folder / "input.txt"),
               "result_sha256": sha(folder / "result.json"),
               "hits_sha256": sha(folder / "hits.jsonl")}
        results.append(row)
        print(json.dumps(row), flush=True)
    save(HERE / "repeat_result.json", {
        "status": "COMPLETE_FOUR_BOUNDED_SAME_TARGET_REPEATS",
        "candidate_id": None, "curve_id": record["curve_id"],
        "public_target_q": record["public_target_q"],
        "target_count": 1,
        "resource_envelope": {"probe_cap_per_repeat": PROBES,
                              "wall_cap_seconds_per_repeat": SECONDS,
                              "rss_cap_bytes": 4 * 1024**3},
        "repeats": results,
        "source_sha256": {"protocol": sha(HERE / "repeat_protocol.json"),
                          "script": sha(Path(__file__))}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "run"))
    {"freeze": freeze, "run": run}[parser.parse_args().mode]()
