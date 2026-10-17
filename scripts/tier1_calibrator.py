#!/usr/bin/env python3
"""Deterministic 32 MiB CPU workload for paired A/A noise checks."""

import hashlib
import time


CALIBRATION_ID = "sha256-32m-v1"
EXPECTED = "b4ce437f949765dce16ec0d6c6b7c5a1d4ef209874ce9f04ee42984c06f14b40"


def main():
    data = bytes(range(256)) * 4096
    state = bytes(32)
    start = time.perf_counter_ns()
    for _ in range(32):
        state = hashlib.sha256(state + data).digest()
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    digest = state.hex()
    if digest != EXPECTED:
        raise SystemExit("calibration checksum mismatch")
    print(f"verified=1 online_ms={elapsed_ms:.6f} calibration_id={CALIBRATION_ID} digest={digest}")


if __name__ == "__main__":
    main()
