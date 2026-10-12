#!/usr/bin/env python3
"""Count online tree-search comparisons removed by the cached plans."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INPUT = ROOT / "prime-j0-sector-digit-20261010/fresh-inputs.json"
NATIVE = ROOT / "prime-j0-secp256k1-native"
SCREEN = NATIVE / "unit_orbit_windows_screen.py"
PRIOR = ROOT / "prime-j0-gauge-tree-20261012/model.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    sys.path.insert(0, str(NATIVE.resolve()))
    spec = importlib.util.spec_from_file_location("gauge_plan_screen", SCREEN)
    screen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(screen)
    inputs = json.loads(INPUT.read_text())
    prior = json.loads(PRIOR.read_text())
    assert prior["input_sha256"] == digest(INPUT)
    atlases = {width: screen.OrbitAtlas(width) for width in (9, 10)}
    terms = Counter()
    patterns = Counter()
    dynamic_candidates = 0
    for scalar_hex in inputs["scalars_hex"]:
        scalar = int(scalar_hex, 16)
        representative = tuple(screen.hex_choices(scalar)[0][2:4])
        codes = [unit for _, unit, active in screen.recode(representative, atlases)
                 if active]
        n = len(codes)
        terms[n] += 1
        patterns[tuple(sum(code // 2 == gauge for code in codes)
                       for gauge in range(3))] += 1
        dynamic_candidates += n * (n + 1) * (n - 1) // 3
    assert sum(terms.values()) == prior["totals"]["cases"] == 4096
    assert sum(n * count for n, count in terms.items()) == prior["totals"]["terms"]
    assert dynamic_candidates == 3_727_178
    log = (HERE / "panel-test.txt").read_text()
    match = re.search(r"cached_gauge_cases=(\d+) rotations=(\d+) "
                      r"product_depth=(\d+) retained_bytes=(\d+)", log)
    assert match and tuple(map(int, match.groups())) == (
        4096, 12886, 201965, 64342768)
    assert log.count("... ok") == 3
    result = {
        "schema": 1, "status": "independently_replayed",
        "kind": "online_selector_work_screen",
        "cases": 4096, "active_term_histogram": dict(sorted(terms.items())),
        "distinct_gauge_patterns": len(patterns),
        "dynamic_pair_gauge_scores": dynamic_candidates,
        "cached_pair_gauge_scores": 0,
        "all_feasible_gauge_patterns": 680,
        "plan_bytes": 28_560,
        "retained_bytes": 64_342_768,
        "input_sha256": digest(INPUT),
        "prior_model_sha256": digest(PRIOR),
        "native_panel_log_sha256": digest(HERE / "panel-test.txt"),
        "source_sha256": digest(Path(__file__)),
    }
    (HERE / "screen.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "cases", "active_term_histogram", "distinct_gauge_patterns",
        "dynamic_pair_gauge_scores", "retained_bytes")}, sort_keys=True))


if __name__ == "__main__":
    main()
