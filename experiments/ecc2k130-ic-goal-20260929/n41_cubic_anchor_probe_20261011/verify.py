"""Independent receipt and satisfiable-control audit for the N41 anchor probe."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parent / "n41_transport_cubic_s8_20261011"
sys.path.insert(0, str(UPSTREAM))
import run as prior  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


protocol = json.loads((HERE / "protocol.json").read_text())
result = json.loads((HERE / "screen_result.json").read_text())
case = json.loads((HERE / "control.result.json").read_text())
fixture = prior.fixture()
assert protocol["source_sha256"]["probe.py"] == sha(HERE / "probe.py")
assert protocol["source_sha256"]["upstream_run.py"] == sha(UPSTREAM / "run.py")
assert protocol["source_sha256"]["upstream_circuit.py"] == sha(UPSTREAM / "circuit.py")
assert protocol["source_sha256"]["upstream_fixture.json"] == sha(UPSTREAM / "fixture.json")
assert protocol["source_sha256"]["solver"] == sha(prior.SOLVER)
assert result["protocol_sha256"] == sha(HERE / "protocol.json")
assert result["status"] == "STOP_AFTER_CONTROL"
assert result["cases"] == [case]
assert case["anchor"] == fixture["known_masks"][0]
assert case["status"] == "BOUNDED_UNKNOWN"
assert case["stop_reason"] == "PARENT_CAP"
assert case["formula_sha256"] == sha(HERE / "control.xcnf")
assert case["stdout_sha256"] == sha(HERE / "control.stdout.txt")
assert case["stderr_sha256"] == sha(HERE / "control.stderr.txt")
assert case["solver_seconds"] >= protocol["control_cap_seconds"]
assert case["peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
stdout = (HERE / "control.stdout.txt").read_text()
assert "s SATISFIABLE" not in stdout and "s UNSATISFIABLE" not in stdout
assert "c " in stdout

circuit, metadata, _ = prior.build(protocol["target_preimages"])
for bit, wire in enumerate(metadata["masks"][0]):
    circuit.clauses.append(f"{wire if case['anchor'] >> bit & 1 else -wire} 0")
assert circuit.next_var - 1 == case["variables"]
assert len(circuit.clauses) == case["clauses"]
assert len(circuit.xors) == case["xor_rows"]
initial = {}
for wires, number in zip(metadata["masks"], fixture["known_masks"]):
    initial.update({wire: number >> bit & 1 for bit, wire in enumerate(wires)})
for wires, number in zip(metadata["pair_z"], fixture["pair_reciprocals"]):
    initial.update({wire: number >> bit & 1 for bit, wire in enumerate(wires)})
for wires, number in zip(metadata["middle_z"], fixture["middle_reciprocals"]):
    initial.update({wire: number >> bit & 1 for bit, wire in enumerate(wires)})
for wire, bit in zip(metadata["branch"], fixture["branch_bits"]):
    initial[wire] = bit
for bit, wire in enumerate(metadata["target_flags"]):
    initial[wire] = fixture["known_raw_preimage_index"] >> bit & 1
assert len(initial) == len(metadata["primary_variables"])
checks = prior.check_assignment(circuit, prior.complete_assignment(circuit, initial))
assert checks == {"clauses": case["clauses"], "native_xor_rows": case["xor_rows"]}
record = {"status": "PASS_SATISFIABLE_ANCHOR_FORMULA_CENSORED_SEARCH",
          "formula_sha256": case["formula_sha256"],
          "checked_assignment": checks,
          "solver_search_logged": True,
          "parent_cap_seconds": protocol["control_cap_seconds"] +
          protocol["parent_margin_seconds"],
          "peak_combined_rss_bytes": case["peak_combined_rss_bytes"],
          "protocol_sha256": sha(HERE / "protocol.json"),
          "case_sha256": sha(HERE / "control.result.json")}
with (HERE / "audit.json").open("x") as stream:
    json.dump(record, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps(record))
