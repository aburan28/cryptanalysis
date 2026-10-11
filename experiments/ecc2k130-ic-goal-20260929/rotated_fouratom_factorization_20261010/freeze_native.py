"""Freeze the split-quartic native replay before query timing."""

import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010"
paths = {"driver": HERE / "native_split.cpp", "binary": HERE / "native_split",
         "header": HERE / "factor_terms.hpp", "factor": HERE / "n131_positive.json",
         "legacy_source": SOURCE / "native.cpp", "legacy_terms": SOURCE / "rotated_terms.hpp",
         "input": SOURCE / "input_n131_positive.txt", "runner": HERE / "run_split.py"}
record = {"status": "FROZEN_BEFORE_N131_SPLIT_QUARTIC_PRODUCT_SCAN",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in paths.items()},
          "workers": 1, "query_cap_seconds": 100, "parent_cap_seconds": 110,
          "rss_cap_bytes": 4294967296,
          "compiler": subprocess.check_output(["clang++", "--version"], text=True).splitlines()[0],
          "platform": platform.platform(),
          "comparison_scope": "same fixed-output component against archived degree-eight native scan; unisolated stage timing"}
with (HERE / "native_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
