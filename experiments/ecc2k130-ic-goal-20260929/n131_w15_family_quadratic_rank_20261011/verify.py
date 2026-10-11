"""Audit the source-frozen N131 W15 degree-two rank certificate."""

import hashlib
import json
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    replay = json.loads((HERE / "sage_replay.json").read_text())
    assert protocol["status"] == "FROZEN_N131_W15_FIXED_PAIR_QUADRATIC_RANK"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in run.source_paths().items()}
    assert protocol["factor_base_B"] == 197292
    assert protocol["trace_support"] == [0, 129]
    assert protocol["feature_dimension"] == run.FEATURE_DIM == 8516
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["status"] == "COMPLETE_QUADRATIC_RANK"
    assert result["stop_reason"] is None and result["full_rank"]
    assert result["rank"] == len(result["pivot_witnesses"]) == 8516
    assert result["right_rows_processed"] == 4259
    assert result["output_rows_processed"] == 8518
    assert result["positive_control_found"]
    assert result["elapsed_seconds_exploratory"] < protocol["wall_cap_seconds"]
    assert result["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert replay["status"] == "PASS_N131_W15_QUADRATIC_RANK_SAGE_REPLAY"
    assert replay["independent_rank"] == replay["s3_witnesses_checked"] == 8516
    assert replay["right_table_rows_checked"] == protocol["right_table_rows"] == 8288
    for name, digest in replay["source_sha256"].items():
        path = (run.SEEDWISE / name if name == "table.tsv" else
                run.AFFINE / "sage_replay.json" if name == "affine_sage_replay.json" else
                HERE / name)
        assert sha(path) == digest, name
    receipt = {"status": "PASS_N131_W15_QUADRATIC_RANK_ARCHIVE",
               "curve_id": protocol["curve_id"],
               "candidate_id": None,
               "feature_dimension": protocol["feature_dimension"],
               "independent_rank": replay["independent_rank"],
               "right_rows_processed": result["right_rows_processed"],
               "output_rows_processed": result["output_rows_processed"],
               "elapsed_seconds_exploratory": result["elapsed_seconds_exploratory"],
               "peak_rss_bytes": result["peak_rss_bytes"],
               "source_sha256": {name: sha(HERE / name) for name in
                                 ("protocol.json", "result.json",
                                  "sage_replay.json", "sage_runtime_info.json")}}
    (HERE / "terminal_audit.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "rank": receipt["independent_rank"]}))


if __name__ == "__main__":
    main()
