"""Independently count held-out seven-seed decisions and paired differences."""

import hashlib
import json
import math
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
ARMS = ("baseline", "public", "one_pair_residual", "two_pair_residual", "joint")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    protocol = load(HERE / "protocol.json")
    receipt = load(HERE / "run_receipt.json")
    assert receipt["status"] == "COMPLETE" and receipt["returncode"] == 0
    assert receipt["protocol_sha256"] == digest(HERE / "protocol.json")
    assert receipt["predictions_sha256"] == digest(HERE / "predictions.tsv")
    assert receipt["stdout_sha256"] == digest(HERE / "stdout.txt")
    assert receipt["stderr_sha256"] == digest(HERE / "stderr.txt")
    assert receipt["peak_child_rss_bytes"] < protocol["rss_cap_bytes"]
    assert receipt["parent_wall_ns_exploratory"] < protocol["parent_cap_seconds"] * 1_000_000_000
    files = {"source": HERE / "forest.cpp", "binary": HERE / "forest",
             "runner": HERE / "run.py", "residual_rows": run.RESIDUAL / "residuals.tsv",
             "residual_protocol": run.RESIDUAL / "extract_protocol_v2.json",
             "residual_receipt": run.RESIDUAL / "extract_receipt_v2.json",
             "prior_result": run.PRIOR / "fit_result.json",
             "prior_audit": run.PRIOR / "terminal_audit.json"}
    assert protocol["source_sha256"] == {name: digest(path) for name, path in files.items()}
    prior = load(run.PRIOR / "fit_result.json")
    baseline = prior["baseline_top_seven"]
    counts = {arm: 0 for arm in ARMS}
    top_one = {arm: 0 for arm in ARMS}
    changed_sets = {arm: 0 for arm in ARMS[1:]}
    discord = {arm: {"arm_only": 0, "baseline_only": 0} for arm in ARMS[1:]}
    count = 0
    with (run.RESIDUAL / "residuals.tsv").open() as source, (HERE / "predictions.tsv").open() as predicted:
        assert source.readline().rstrip("\n") == "x\ty\tr0x\tr0y\tr01x\tr01y\tseed_a\tseed_b\tp0\tp1"
        assert predicted.readline().rstrip("\n") == "row\tseed\t" + "\t".join(ARMS)
        for index, source_line in enumerate(source):
            if index < 80000:
                continue
            parts = predicted.readline().rstrip("\n").split("\t")
            assert len(parts) == 7 and int(parts[0]) == index
            seed = int(source_line.split("\t")[6])
            assert seed == int(parts[1]) and 1 <= seed <= 63
            found = {}
            for arm, raw in zip(ARMS, parts[2:]):
                top = [int(value) for value in raw.split(",")]
                assert len(top) == 7 and len(set(top)) == 7
                assert all(1 <= value <= 63 for value in top)
                if arm == "baseline":
                    assert top == baseline
                found[arm] = seed in top
                counts[arm] += found[arm]
                top_one[arm] += seed == top[0]
                if arm != "baseline":
                    changed_sets[arm] += set(top) != set(baseline)
            for arm in ARMS[1:]:
                discord[arm]["arm_only"] += found[arm] and not found["baseline"]
                discord[arm]["baseline_only"] += found["baseline"] and not found[arm]
            count += 1
        assert predicted.readline() == ""
    assert count == 20000 and counts["baseline"] == prior["top_seven"]["prior_only"] == 4465
    paired = {}
    for arm in ARMS[1:]:
        a = discord[arm]["arm_only"]
        b = discord[arm]["baseline_only"]
        delta = (a - b) / count
        # The paired outcome takes values +1, 0, -1.
        se = math.sqrt(max(0.0, ((a+b)/count-delta*delta) / (count-1)))
        paired[arm] = {"difference": delta,
                       "normal95": [delta-1.959963984540054*se,
                                    delta+1.959963984540054*se],
                       **discord[arm]}
    result = {"status": "VERIFIED_HELDOUT", "protocol_sha256": digest(HERE / "protocol.json"),
              "run_receipt_sha256": digest(HERE / "run_receipt.json"),
              "predictions_sha256": digest(HERE / "predictions.tsv"),
              "holdout_count": count, "seven_seed_hits": counts,
              "top_one_hits": top_one, "changed_seven_seed_sets": changed_sets,
              "paired_vs_baseline": paired}
    (HERE / "audit.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "seven_seed_hits": counts}, sort_keys=True))


if __name__ == "__main__":
    main()
