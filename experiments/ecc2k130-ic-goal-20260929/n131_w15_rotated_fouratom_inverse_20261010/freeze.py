"""Freeze the universal derivation inputs after recording the checked Sage runtime."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010/resultant_terms.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


record = {"status": "FROZEN_BEFORE_ROTATED_RESULTANT_DERIVATION",
          "source_sha256": {"derive.py": sha(HERE / "derive.py"),
                            "old_resultant": sha(OLD),
                            "sage_runtime_info": sha(HERE / "sage_runtime_info.json")},
          "method": "Res_c(g_a(p,c), Res_d(g_b(q,d), U(c,d,z))) over GF(2)",
          "one_worker": True}
with (HERE / "protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
