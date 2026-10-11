"""Freeze W6/W15 trace source and corrected public lift inputs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
paths = {"source_trace": HERE / "source_trace.py", "corrected": HERE / "result.json",
         "n41_source": ROOT / "n41_n131_diagonal_atom_20261010" / "screen.json",
         "n131_trace": ROOT / "n131_w15_middle_trace_public_gate_20261010" / "trace_proof.json",
         "n131_census": ROOT / "n131_w15_cofactor_class_gate_20261010" / "census.json"}
record = {"status": "FROZEN_BEFORE_W6_W15_TARGET_LIFT_TRACE_GATE",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in paths.items()},
          "scope": "exact characteristic-two 2-descent character on the two source geometries"}
with (HERE / "source_trace_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
