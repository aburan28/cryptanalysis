#!/usr/bin/env python3
"""Generate a fresh panel disjoint from all earlier holdouts and the design panel."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "prime-j0-axis152-20261012"))
import holdout2 as independent  # noqa: E402

FROZEN_COMMIT = "3bb8bace32d5ba549888e7118d201ae5c2aecfd8"
SEED = int.from_bytes(sha256(bytes.fromhex(FROZEN_COMMIT)).digest()[:8], "big")
CASES = 512
OUTPUT = HERE / "holdout.json"
DESIGN = EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json"
PRIOR = (
    EXP / "prime-j0-axis416-20261012/holdout.json",
    EXP / "prime-j0-axis152-20261012/holdout.json",
    EXP / "prime-j0-axis152-20261012/holdout2.json",
    EXP / "prime-j0-axis152-xyzz-20261012/holdout.json",
    EXP / "prime-j0-axis152-xyzz-20261012/holdout2.json",
    EXP / "prime-j0-axis152-solinas-20261012/holdout.json",
    EXP / "prime-j0-axis286-20261012/holdout.json",
    EXP / "prime-j0-power2-direct-terminal-20261012/holdout.json",
    EXP / "prime-j0-power2-direct-terminal-20261012/holdout2.json",
    EXP / "prime-j0-hex-terminal-20261012/holdout.json",
    EXP / "prime-j0-hex-tree-20261013/holdout.json",
    EXP / "prime-j0-hex-workdepth-20261013/holdout.json",
)


def make() -> dict:
    rng = random.Random(SEED)
    scalars = [rng.getrandbits(256) % independent.ORDER for _ in range(CASES)]
    assert len(set(scalars)) == CASES
    design_raw = DESIGN.read_bytes()
    design = json.loads(design_raw)
    assert design["count"] == len(design["scalars_hex"]) == 4096
    assert set(scalars).isdisjoint(int(value, 16) % independent.ORDER
                                   for value in design["scalars_hex"])
    prior_hashes = {}
    for path in PRIOR:
        raw = path.read_bytes()
        values = json.loads(raw)
        previous = values.get("scalars_hex")
        if previous is None:
            previous = [case["scalar_hex"] for case in values["cases"]]
        assert set(scalars).isdisjoint(int(value, 16) % independent.ORDER for value in previous)
        prior_hashes[str(path.relative_to(EXP))] = sha256(raw).hexdigest()
    cases = []
    for index, scalar in enumerate(scalars):
        point = independent.multiply(scalar)
        cases.append({
            "index": index, "scalar_hex": f"{scalar:064x}",
            "base_x_hex": f"{independent.GX:064x}",
            "base_y_hex": f"{independent.GY:064x}",
            "expected_identity": point is None,
            "expected_x_hex": None if point is None else f"{point[0]:064x}",
            "expected_y_hex": None if point is None else f"{point[1]:064x}",
        })
    scalar_bytes = b"".join(value.to_bytes(32, "big") for value in scalars)
    return {
        "schema": 1, "curve": "secp256k1", "seed": SEED,
        "frozen_evaluator_commit": FROZEN_COMMIT,
        "input_law": "512 distinct random.Random(seed).getrandbits(256) % subgroup_order scalars",
        "scalar_sha256": sha256(scalar_bytes).hexdigest(),
        "disjoint_prior_panels_sha256": prior_hashes,
        "disjoint_design_sha256": sha256(design_raw).hexdigest(),
        "generator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": cases,
    }


def main() -> None:
    data = (json.dumps(make(), sort_keys=True, separators=(",", ":")) + "\n").encode()
    if "--check" in sys.argv:
        assert OUTPUT.read_bytes() == data
    else:
        if OUTPUT.exists():
            raise SystemExit("holdout exists; use --check")
        OUTPUT.write_bytes(data)
    print(f"holdout_cases={CASES} sha256={sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
