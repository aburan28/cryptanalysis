#!/usr/bin/env python3
"""Generate the exact norm-4096 tail for the linked nine-orbit atlas.

All transition costs and serialization are shared with the original atlas
generator. Only the digit representatives differ. The generator audits every
decoded state and refuses to replace a frozen table with different bytes.
"""

from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
import generate_shared_z_tail as tail


tail.TABLE = digit_table(SEEDS[2])
tail.TARGET = Path(__file__).resolve().parent / "linked-shared-z-tail4096.bin"


if __name__ == "__main__":
    tail.main()
