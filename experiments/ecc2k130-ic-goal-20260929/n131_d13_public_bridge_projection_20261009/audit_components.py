#!/usr/bin/env python3
"""Check exact d13 public-Q bridge and projected native-XOR components."""

import hashlib
import json
from pathlib import Path

from audit_bridge import xor_components

HERE = Path(__file__).resolve().parent
BRIDGE = HERE / "bridge_cnf/bridge_cnf.xcnf"
PROJECTED = HERE / "budget1/projected.xcnf"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    output = HERE / "component_audit.json"
    if output.exists():
        raise FileExistsError(output)
    bridge = json.loads((HERE / "bridge_cnf/independent_audit.json").read_text())
    projection = json.loads((HERE / "budget1/result.json").read_text())
    elimination = json.loads((HERE / "budget1/independent_elimination_audit.json").read_text())
    if (bridge["status"] != "PASS_EQUIVALENT_AND_COMPONENT_FIT" or
            projection["status"] != "PASS" or elimination["status"] != "PASS" or
            sha(BRIDGE) != projection["source_sha256"]["input_xcnf"] or
            sha(PROJECTED) != projection["source_sha256"]["projected_xcnf"]):
        raise ValueError("source transform or independent audit differs")
    bridge_components = xor_components(BRIDGE)
    projected_components = xor_components(PROJECTED)
    if (bridge_components["xor_rows"] != projection["original_xor_rows"] or
            projected_components["xor_rows"] != projection["projected_xor_rows"]):
        raise ValueError("component row accounting differs")
    fits = all(item["max_rows"] <= 10000 and item["max_columns"] <= 15000
               for item in (bridge_components, projected_components))
    result = {
        "kind": "n131_d13_public_q_exact_bridge_projected_component_audit",
        "status": "PASS_COMPONENT_FIT" if fits else "COMPONENT_EXCEEDS_LIMIT",
        "bridge": bridge_components,
        "projected": projected_components,
        "source_sha256": {
            "bridge_xcnf": sha(BRIDGE), "projected_xcnf": sha(PROJECTED),
            "bridge_audit": sha(HERE / "bridge_cnf/independent_audit.json"),
            "elimination_audit": sha(HERE / "budget1/independent_elimination_audit.json"),
            "auditor": sha(Path(__file__)),
        },
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "bridge_max_rows": bridge_components["max_rows"],
                      "projected_max_rows": projected_components["max_rows"],
                      "projected_max_columns": projected_components["max_columns"]}))


if __name__ == "__main__":
    main()
