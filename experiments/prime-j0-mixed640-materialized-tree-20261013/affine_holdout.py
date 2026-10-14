#!/usr/bin/env python3
"""Generate or verify a fresh panel after the 128-byte affine-pair source is frozen."""

from hashlib import sha256
import json
from pathlib import Path
import random
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "prime-j0-tau-power16-20261010"))
import verify_group as reference  # noqa: E402
sys.path.insert(0, str(HERE.parent / "prime-j0-mixed-radix640-20261010"))
from make_inputs import N, SOURCES  # noqa: E402


def digest(data):
    return sha256(data).hexdigest()


def main():
    assert sys.argv[1:] in (["--generate"], ["--check"])
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()
    source = {name: digest((HERE / name).read_bytes()) for name in
              ("native_overlay.py", "native_variant.rs", "native_affine128.py",
               "affine_holdout.py")}
    old_panels = list(SOURCES) + ["prime-j0-mixed-radix640-20261010/fresh-inputs.json"]
    prior_hashes = {}
    seen = set()
    for name in old_panels:
        raw = (HERE.parent / name).read_bytes()
        prior_hashes[name] = digest(raw)
        seen.update(int(x, 16) % N for x in json.loads(raw)["scalars_hex"])
    original = HERE / "holdout.json"
    prior_hashes["holdout.json"] = digest(original.read_bytes())
    seen.update(int(x["scalar_hex"], 16) % N for x in json.loads(original.read_bytes())["cases"])
    hybrid = HERE / "hybrid-holdout.json"
    prior_hashes["hybrid-holdout.json"] = digest(hybrid.read_bytes())
    seen.update(int(x["scalar_hex"], 16) % N for x in json.loads(hybrid.read_bytes())["cases"])
    prior_seen = seen.copy()
    target = HERE / "affine-holdout.json"
    if sys.argv[1] == "--generate":
        assert not target.exists()
        for name, expected in source.items():
            raw = subprocess.check_output(
                ["git", "show", f"{head}:experiments/{HERE.name}/{name}"], cwd=ROOT)
            assert digest(raw) == expected
        rng = random.Random(int(head[:16], 16) ^ 0xA128)
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
        record = {"schema": 1, "source_commit": head, "source_sha256": source,
                  "prior_input_sha256": prior_hashes, "cases": cases}
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    record = json.loads(target.read_bytes())
    assert record["schema"] == 1 and record["source_sha256"] == source
    assert record["prior_input_sha256"] == prior_hashes
    assert len(record["cases"]) == 128
    for name, expected in source.items():
        raw = subprocess.check_output(
            ["git", "show", f"{record['source_commit']}:experiments/{HERE.name}/{name}"], cwd=ROOT)
        assert digest(raw) == expected
    selected = set()
    for case in record["cases"]:
        residue = int(case["scalar_hex"], 16) % N
        assert residue not in prior_seen and residue not in selected
        selected.add(residue)
        point = reference.multiply(residue, reference.G)
        assert case["point_hex"] == f"{point[0]:064x}:{point[1]:064x}"
    print(json.dumps({"status": "passed", "cases": len(record["cases"]),
                      "fixture_sha256": digest(target.read_bytes()),
                      "source_commit": record["source_commit"]}, sort_keys=True))


if __name__ == "__main__":
    main()
