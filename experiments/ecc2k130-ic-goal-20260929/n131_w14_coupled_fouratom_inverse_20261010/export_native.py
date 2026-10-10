#!/usr/bin/env python3
"""Export the frozen Sage controls for the native field kernel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inputs = json.loads((HERE / "inputs.json").read_text())
    assert inputs["status"] == "PASS_FROZEN_FOUR_ATOM_OUTPUT_CONTROLS"
    paths = {}
    for n in (41, 131):
        panel = inputs["panels"][str(n)]
        assert panel["source_mask_sum"] == 1 and panel["source_sum_field"] == 2
        for kind, key in (("positive", "positive_z"),
                          ("trace_zero_control", "trace_zero_control_z")):
            path = HERE / f"native_n{n}_{kind}.txt"
            with path.open("x") as out:
                out.write(f"{n} {panel['source_dimension']} 2 {panel[key]}\n")
            paths[path.name] = sha(path)
    result = {"status": "PASS_NATIVE_PANEL_EXPORT",
              "source_sha256": {"script": sha(Path(__file__)),
                                "inputs": sha(HERE / "inputs.json"),
                                **paths}}
    with (HERE / "native_export.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "inputs": len(paths)}))


if __name__ == "__main__":
    main()
