#!/usr/bin/env python3
"""Use ten evenly spaced two-x rows within the same 32 MiB table cap."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "99b6323f52f2f6eb7e4a8a2c4056ad7b9ebce29571a9ec4187fd4212097a3756"
WINDOWS_SHA256 = "71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d"


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f, w = front.read_text(), windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256
    begin = w.index("struct SplitPrimeCacheBudgetTables {")
    end = w.index("static SPLIT_PRIME_CACHE_BUDGET_TABLES:", begin)
    block = w[begin:end]
    assert block.count("if index % 2 == 0") == 1
    assert block.count(".count(), 7") == 1
    block = block.replace("if index % 2 == 0", "if index % 3 != 2")
    block = block.replace(".count(), 7", ".count(), 10")
    w = w[:begin] + block + w[end:]
    windows.write_text(w)
    print("front_sha256=" + sha256(f.encode()).hexdigest())
    print("windows_sha256=" + sha256(w.encode()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
