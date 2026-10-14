#!/usr/bin/env python3
"""Generate or check a disjoint native panel after source commit freeze."""

from hashlib import sha256
import json
from pathlib import Path
import random
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PRIOR = HERE.parent / "prime-j0-mixed-radix640-20261010"
sys.path.insert(0, str(HERE.parent / "prime-j0-tau-power16-20261010"))
import verify_group as reference  # noqa: E402
sys.path.insert(0, str(PRIOR))
from make_inputs import N, SOURCES  # noqa: E402


def digest(data):
    return sha256(data).hexdigest()


def main():
    assert sys.argv[1:] in (["--generate"], ["--check"])
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                           text=True).strip()
    source = {name: digest((HERE / name).read_bytes()) for name in
              ("native_overlay.py", "native_variant.rs", "holdout.py")}
    seen = set()
    sources = list(SOURCES) + ["prime-j0-mixed-radix640-20261010/fresh-inputs.json"]
    prior_hashes = {}
    for name in sources:
        raw = (HERE.parent / name).read_bytes()
        prior_hashes[name] = digest(raw)
        seen.update(int(x, 16) % N for x in json.loads(raw)["scalars_hex"])
    prior_seen = seen.copy()
    target = HERE / "holdout.json"
    if sys.argv[1] == "--generate":
        assert not target.exists()
        for name in source:
            committed = subprocess.check_output(
                ["git", "show", f"{current_head}:experiments/{HERE.name}/{name}"],
                cwd=ROOT)
            assert digest(committed) == source[name]
        rng = random.Random(int(current_head[:16], 16))
        cases = []
        while len(cases) < 128:
            scalar = rng.getrandbits(256)
            residue = scalar % N
            if residue in seen:
                continue
            seen.add(residue)
            point = reference.multiply(residue, reference.G)
            assert point is not None
            cases.append({"scalar_hex": f"{scalar:064x}",
                          "point_hex": f"{point[0]:064x}:{point[1]:064x}"})
        record = {"schema": 1, "source_commit": current_head, "source_sha256": source,
                  "prior_input_sha256": prior_hashes, "cases": cases}
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    record = json.loads(target.read_bytes())
    assert record["schema"] == 1
    assert record["source_sha256"] == source
    assert record["prior_input_sha256"] == prior_hashes
    assert len(record["cases"]) == 128
    for name in source:
        committed = subprocess.check_output(
            ["git", "show", f"{record['source_commit']}:experiments/{HERE.name}/{name}"],
            cwd=ROOT)
        assert digest(committed) == source[name]
    scalar_set = set()
    for case in record["cases"]:
        scalar = int(case["scalar_hex"], 16)
        residue = scalar % N
        assert residue not in scalar_set and residue not in prior_seen
        scalar_set.add(residue)
        point = reference.multiply(residue, reference.G)
        assert case["point_hex"] == f"{point[0]:064x}:{point[1]:064x}"
    print(json.dumps({"status": "passed", "cases": len(record["cases"]),
                      "fixture_sha256": digest(target.read_bytes()),
                      "source_commit": record["source_commit"]}, sort_keys=True))


if __name__ == "__main__":
    main()
