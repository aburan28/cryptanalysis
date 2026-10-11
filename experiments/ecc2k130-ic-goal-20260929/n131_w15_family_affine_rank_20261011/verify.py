"""Audit frozen fixed-seed family rank and independent checked-Sage replay."""

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
    assert protocol["status"] == "FROZEN_N131_W15_FIXED_FIRST_PAIR_AFFINE_RANK"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in run.source_paths().items()}
    assert result["source_protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["status"] == "COMPLETE_N131_W15_FIXED_FIRST_PAIR_AFFINE_RANK"
    assert result["right_rows"] == protocol["right_row_cap"] == 512
    assert result["output_rows"] == 2 * result["right_rows"] == 1024
    assert result["linear_rank"] == len(result["linear_rank_witnesses"]) == 130
    assert result["affine_rank"] == len(result["affine_rank_witnesses"]) == 131
    assert result["positive_root"]["output_z"] == protocol["positive_four_atom_reciprocal"]
    assert replay["status"] == "PASS_N131_W15_FIXED_SEED_AFFINE_RANK_SAGE_REPLAY"
    assert replay["linear_rank"] == 130 and replay["affine_rank"] == 131
    assert replay["s3_witness_rows_replayed"] == 261
    assert len(replay["group_replay"]) == 2
    for name, digest in replay["source_sha256"].items():
        path = (HERE / name if name not in ("table.tsv", "w15_lift.py")
                else run.SEEDWISE / name if name == "table.tsv"
                else run.GOAL / "n131_w15_coupled_sixpair_20261010/w15_lift.py")
        assert sha(path) == digest, name
    audit = {"status": "PASS_N131_W15_FIXED_SEED_AFFINE_RANK_ARCHIVE",
             "curve_id": protocol["curve_id"], "seed_mask": protocol["seed_mask"],
             "first_pair_reciprocal": protocol["fixed_first_reciprocal"],
             "right_rows": result["right_rows"], "output_rows": result["output_rows"],
             "trace_zero_linear_bound": 130,
             "observed_linear_rank": result["linear_rank"],
             "observed_affine_augmented_rank": result["affine_rank"],
             "source_sha256": {name: sha(HERE / name) for name in
                               ("protocol.json", "result.json", "sage_replay.json",
                                "sage_runtime_info.json")}}
    (HERE / "terminal_audit.json").write_text(json.dumps(audit, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": audit["status"], "rank": audit["observed_linear_rank"]}))


if __name__ == "__main__":
    main()
