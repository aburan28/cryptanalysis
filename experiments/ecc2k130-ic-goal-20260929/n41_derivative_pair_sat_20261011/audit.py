"""Check frozen formula identity and terminal meaning of every solver row."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


p = json.loads((HERE / "protocol.json").read_text())
s = json.loads((HERE / "solver_protocol.json").read_text())
m = json.loads((HERE / "matrix_protocol.json").read_text())
assert s["protocol_sha256"] == sha(HERE / "protocol.json")
assert m["base_protocol_sha256"] == sha(HERE / "protocol.json")
assert p["sha256"]["circuit"] == sha(HERE / "circuit.py")
assert p["sha256"]["prepare"] == sha(HERE / "prepare.py")
assert s["runner_sha256"] == sha(HERE / "solve.py")
assert m["source_sha256"] == sha(HERE / "matrix_probe.py")
rows = []
for label in ("positive", "control_0", "control_1"):
    shape = p["formulas"][label]
    assert shape["sha256"] == sha(HERE / f"{label}.xcnf")
    r = json.loads((HERE / f"{label}.json").read_text())
    stdout = (HERE / f"{label}.stdout").read_bytes()
    assert r["stdout_sha256"] == sha(HERE / f"{label}.stdout")
    assert r["stderr_sha256"] == sha(HERE / f"{label}.stderr")
    assert r["status"] == "BOUNDED_UNKNOWN"
    assert r["killed_by"] == "PARENT_TIME_CAP"
    assert r["return_code"] == -9
    assert r["wall_ns"] >= 35_000_000_000
    assert r["peak_combined_rss_bytes"] < p["rss_cap_bytes"]
    assert b'c rst ' in stdout and b's SATISFIABLE' not in stdout
    assert b's UNSATISFIABLE' not in stdout
    rows.append({"label": label, "status": r["status"],
                 "wall_ns": r["wall_ns"],
                 "peak_combined_rss_bytes": r["peak_combined_rss_bytes"],
                 "formula_bytes": shape["bytes"],
                 "and_gates": shape["and_gates"],
                 "variables": shape["variables"],
                 "native_xor_rows": shape["native_xor_rows"]})
mr = json.loads((HERE / "matrix_positive.json").read_text())
stdout = (HERE / "matrix_positive.stdout").read_bytes()
assert mr["status"] == "BOUNDED_UNKNOWN" and mr["killed_by"] == "PARENT_TIME_CAP"
assert mr["stdout_sha256"] == sha(HERE / "matrix_positive.stdout")
assert mr["stderr_sha256"] == sha(HERE / "matrix_positive.stderr")
assert b'Using 1 matrices' in stdout and b'c rst ' in stdout
assert b's SATISFIABLE' not in stdout and b's UNSATISFIABLE' not in stdout
assert mr["peak_combined_rss_bytes"] < p["rss_cap_bytes"]
output = {"status": "PASS_DERIVATIVE_N41_RECEIPT_AUDIT",
          "positive_full_assignment": p["positive_full_assignment"],
          "rows": rows, "wide_matrix_positive": mr,
          "protocol_sha256": sha(HERE / "protocol.json")}
(HERE / "audit.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
print(output["status"])
