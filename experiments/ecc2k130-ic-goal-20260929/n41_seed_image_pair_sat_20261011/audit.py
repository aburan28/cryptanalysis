"""Audit the frozen seed-image formulas and bounded solver rows."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


p = json.loads((HERE / "protocol.json").read_text())
s = json.loads((HERE / "solver_protocol.json").read_text())
assert p["status"] == "FROZEN_N41_SEED_IMAGE_PAIR_SAT"
assert p["positive_full_assignment"] == "PASS"
assert s["status"] == "FROZEN_BEFORE_UNPINNED_SOLVES"
assert s["protocol_sha256"] == sha(HERE / "protocol.json")
assert s["runner_sha256"] == sha(HERE / "solve.py")
assert p["sha256"]["circuit"] == sha(HERE / "circuit.py")
assert p["sha256"]["prepare"] == sha(HERE / "prepare.py")
assert p["sha256"]["derivative_circuit"] == sha(HERE.parent / "n41_derivative_pair_sat_20261011/circuit.py")
assert p["sha256"]["solver"] == sha(p["solver"])
rows = []
for label in ("positive", "control_23", "control_229"):
    shape = p["cases"][label]
    assert shape["sha256"] == sha(HERE / f"{label}.xcnf")
    row = json.loads((HERE / f"{label}.json").read_text())
    stdout = (HERE / f"{label}.stdout").read_bytes()
    assert row["solver_protocol_sha256"] == sha(HERE / "solver_protocol.json")
    assert row["stdout_sha256"] == sha(HERE / f"{label}.stdout")
    assert row["stderr_sha256"] == sha(HERE / f"{label}.stderr")
    assert row["status"] == "BOUNDED_UNKNOWN"
    assert row["killed_by"] == "PARENT_TIME_CAP" and row["return_code"] == -9
    assert row["wall_ns"] >= 35_000_000_000
    assert row["peak_combined_rss_bytes"] < p["rss_cap_bytes"]
    assert b'c rst ' in stdout
    assert b's SATISFIABLE' not in stdout and b's UNSATISFIABLE' not in stdout
    rows.append({"label": label, "status": row["status"],
                 "wall_ns": row["wall_ns"],
                 "peak_combined_rss_bytes": row["peak_combined_rss_bytes"],
                 "formula": shape})
out = {"status": "PASS_SEED_IMAGE_SAT_RECEIPT_AUDIT",
       "candidate_id": None, "positive_assignment": "PASS",
       "rows": rows,
       "baseline_positive_formula": p["baseline_positive_shape"],
       "protocol_sha256": sha(HERE / "protocol.json"),
       "solver_protocol_sha256": sha(HERE / "solver_protocol.json"),
       "source_sha256": sha(__file__)}
(HERE / "audit.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"])
