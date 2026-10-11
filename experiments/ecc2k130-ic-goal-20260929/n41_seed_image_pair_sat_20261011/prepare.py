"""Freeze unpinned target formulas and verify a full positive assignment."""

import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import circuit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "experiments/koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

HELPER = HERE.parent / "n41_derivative_pair_sat_20261011/prepare.py"
spec = importlib.util.spec_from_file_location("frozen_derivative_prepare", HELPER)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


fixture_path = HERE.parent / "n41_two_pair_relaxation_20261011/targets.json"
panel_path = HERE.parent / "n41_target_derived_join_panel_20261011/panel.json"
fixture = json.loads(fixture_path.read_text())
panel = json.loads(panel_path.read_text())
cases = {
    "positive": fixture["known_positive"]["target_z"],
    "control_23": panel["controls"][23]["target_z"],
    "control_229": panel["controls"][229]["target_z"],
}
if (HERE / "protocol.json").exists():
    raise SystemExit("protocol exists")
shapes = {}
for label, target_z in cases.items():
    started = time.monotonic_ns()
    c = KaratsubaCircuit(41, [0, 3])
    wires = circuit.build(c, circuit.Field(), target_z)
    build_ns = time.monotonic_ns()-started
    if label == "positive":
        initial = {}

        def bind(bits, number):
            for i, wire in enumerate(bits):
                initial[wire] = (number >> i) & 1

        masks = fixture["known_positive"]["source_masks"]
        for i in range(2):
            a, b = masks[2*i:2*i+2]
            bind(wires["seed"][i], a ^ b)
            bind(wires["first"][i], a)
            bind(wires["pair_z"][i], fixture["known_positive"]["pair_reciprocals"][i])
        assert len(initial) == len(wires["primary_variables"])
        old.check(c, old.complete_assignment(c, initial))
    output = HERE / f"{label}.xcnf"
    c.write(output)
    shapes[label] = {"target_z": target_z, "variables": c.next_var-1,
                     "and_gates": c.and_count, "clauses": len(c.clauses),
                     "native_xor_rows": len(c.xors), "bytes": output.stat().st_size,
                     "sha256": sha(output), "construction_ns": build_ns}

baseline = json.loads((HERE.parent / "n41_derivative_pair_sat_20261011/protocol.json").read_text())
out = {"status": "FROZEN_N41_SEED_IMAGE_PAIR_SAT",
       "candidate_id": None, "utc": datetime.now(timezone.utc).isoformat(),
       "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
       "host": platform.platform(),
       "workers": 1, "solver_cap_seconds": 30, "parent_cap_seconds": 35,
       "rss_cap_bytes": 4*1024**3,
       "solver": "/opt/homebrew/bin/cryptominisat5",
       "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                        "--random=20261011", "--maxtime=30"],
       "positive_full_assignment": "PASS",
       "cases": shapes,
       "baseline_positive_shape": baseline["formulas"]["positive"],
       "sha256": {"circuit": sha(HERE / "circuit.py"),
                  "prepare": sha(HERE / "prepare.py"),
                  "derivative_circuit": sha(circuit.BASE),
                  "assignment_helper": sha(HELPER),
                  "karatsuba": sha(ROOT / "experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py"),
                  "fixture": sha(fixture_path), "panel": sha(panel_path),
                  "solver": sha("/opt/homebrew/bin/cryptominisat5")}}
(HERE / "protocol.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], shapes)
