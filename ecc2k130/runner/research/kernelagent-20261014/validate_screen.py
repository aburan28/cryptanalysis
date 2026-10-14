"""Recompute a production GPU screen's corpus, rate and A/A advancement gate."""

import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys


EXPECTED_COMMIT = "1f8e6847de9e207880bd3be63835c3f56eb182d5"
EXPECTED_CORPUS = "c80bb8db34e419d53bc946a5fef01c99fd60214a16f9b42ff87b5d52f3668a90"


def check_sample(sample: dict) -> float:
    command = sample["command"]
    for flag, value in (("--threads", "120320"), ("--steps", "1024"),
                        ("--launches", "64"), ("--run-id", "11000"),
                        ("--dp-weight", "32")):
        if flag not in command or command[command.index(flag) + 1] != value:
            raise ValueError(f"wrong workload: {flag}")
    if sample["records"] != 355 or sample["sorted_sha256"] != EXPECTED_CORPUS:
        raise ValueError("DP32 corpus differs from frozen control")
    output = sample["output"]
    if "355 distinguished points (0 verified against the reference, 0 dropped)" not in output:
        raise ValueError("missing zero-drop finished line")
    match = re.search(r"finished: ([0-9.]+) M it/s", output)
    if not match:
        raise ValueError("missing native rate")
    rate = float(match.group(1)) / 1000
    if not math.isclose(rate, sample["billions_per_second"], abs_tol=1e-9):
        raise ValueError("stored rate differs from native output")
    return rate


def main(input_name: str, output_name: str) -> None:
    path = Path(input_name)
    output = Path(output_name)
    if output.exists():
        raise FileExistsError(output)
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("mode") != "screen" or data.get("baseline_commit") != EXPECTED_COMMIT:
        raise ValueError("wrong screen or baseline")
    if len(data["variants"]) != 2 or data["variants"][0]["name"] != "production":
        raise ValueError("expected A/A and one production candidate")
    rows = []
    for variant in data["variants"]:
        pairs = variant["pairs"]
        if len(pairs) != 2:
            raise ValueError("expected two alternating pairs")
        ratios = []
        for pair in pairs:
            baseline = check_sample(pair["baseline"])
            candidate = check_sample(pair["candidate"])
            ratio = candidate / baseline
            if not math.isclose(ratio, pair["ratio"], rel_tol=1e-12):
                raise ValueError("stored paired ratio differs from raw rates")
            ratios.append(ratio)
        if not math.isclose(statistics.median(ratios), variant["median_ratio"], rel_tol=1e-12):
            raise ValueError("stored median ratio differs")
        rows.append({"name": variant["name"], "ratios": ratios,
                     "median_ratio": statistics.median(ratios),
                     "binary_sha256": variant["binary_sha256"]})
    result = {
        "input": str(path), "input_sha256": hashlib.sha256(raw).hexdigest(),
        "baseline_commit": EXPECTED_COMMIT, "corpus_sha256": EXPECTED_CORPUS,
        "all_samples_valid": True, "variants": rows,
        "candidate_above_aa_in_both_pairs": all(
            ratio > max(rows[0]["ratios"]) for ratio in rows[1]["ratios"]),
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": str(output),
                      "candidate_above_aa_in_both_pairs": result["candidate_above_aa_in_both_pairs"]}))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: validate_screen.py screen.json validation.json")
    main(sys.argv[1], sys.argv[2])
