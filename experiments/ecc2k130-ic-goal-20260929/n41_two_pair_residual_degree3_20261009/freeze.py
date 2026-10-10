#!/usr/bin/env python3
"""Freeze exact input and source identity before the cubic-rank run."""

import json
from pathlib import Path

import rank

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / "protocol.json"
    if path.exists():
        raise FileExistsError("preserve first frozen protocol")
    record = {"status": "FROZEN", "proposal_id": "Q20261009182400",
              "candidate_id": None, "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
              "target_count": 1, "monomial_degree_max": 3,
              "monomial_dimension": rank.DIM, "max_rows": rank.MAX_ROWS,
              "row_stride": rank.STRIDE, "row_offset": rank.OFFSET,
              "cap_ns": rank.CAP_NS, "rss_cap_bytes": rank.RSS_CAP,
              "source_sha256": {str(item): rank.sha(item)
                                for item in rank.source_paths()}}
    path.write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": "FROZEN", "source_files": len(record["source_sha256"]),
                      "monomial_dimension": rank.DIM}, sort_keys=True))


if __name__ == "__main__":
    main()
