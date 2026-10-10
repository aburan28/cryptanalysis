"""Freeze exact native rotated-resultant controls before the scans."""

import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, text):
    with path.open("x") as output:
        output.write(text)


control = json.loads((HERE / "control_result.json").read_text())
assert control["status"] == "PASS_ROTATED_RESULTANT_N41_PUBLIC_ROW_AND_N131_CONTROL"
inputs = {}
for label, n, d in (("n41",41,6),("n131",131,15)):
    case = control[label]
    r0,r1 = case["pair_rotations"]
    s = case["seed_mask"] << 1
    for kind,z in (("positive",case["four_atom_reciprocal_output"]),
                   ("field_control",case["independent_field_control_z"])):
        name = f"input_{label}_{kind}.txt"
        write_new(HERE / name, f"{n} {d} {r0} {r1} {s} {z}\n")
        inputs[name] = sha(HERE / name)
record = {
    "status": "FROZEN_BEFORE_NATIVE_ROTATED_FOUR_ATOM_SCANS",
    "source_sha256": {name: sha(HERE / name) for name in
                      ("native.cpp", "native", "rotated_terms.hpp", "resultant.json",
                       "control_result.json", "run_native.py", "prepare_native.py")},
    "input_sha256": inputs,
    "native_query_cap_seconds_each": 100,
    "parent_cap_seconds_each": 110,
    "rss_cap_bytes": 4294967296,
    "workers": 1,
    "compiler": subprocess.check_output(["clang++", "--version"], text=True).splitlines()[0],
    "platform": platform.platform(),
}
with (HERE / "native_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
