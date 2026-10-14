#!/usr/bin/env python3
"""Check the existing RDS campaign contract without writing any DP records."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "aws"))
from rds_gpu import Store  # noqa: E402
from protocol import CAMPAIGN, DP_WEIGHT, WALK_ID  # noqa: E402


def main() -> int:
    store = Store()
    try:
        store.register(CAMPAIGN, dp_weight=DP_WEIGHT, walk_id=WALK_ID)
    finally:
        store.close()
    print("existing RDS campaign contract verified", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
