#!/usr/bin/env python3
"""Generate the matched 15-window compact-table benchmark front door."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASE = HERE / "native_bench_cli.py"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"expected one source anchor, found {source.count(old)}: {old[:80]}")
    return source.replace(old, new, 1)


def main(target: Path) -> None:
    spec = importlib.util.spec_from_file_location("mixed640_bench_cli", BASE)
    bench = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(bench)
    bench.main("selective", target)
    target = target.resolve()
    front_path = target / "src/bin/eisenstein_fixed.rs"
    front = front_path.read_text()
    front = replace_once(front,
        "    let retained_bytes = unit_orbit_windows::warm_mixed640_pretau_table();\n",
        "    let retained_bytes = unit_orbit_windows::warm_format(56);\n")
    front = replace_once(front,
        "        unit_orbit_windows::multiply_u256_tau_mixed640_pretau_tree(\n",
        "        unit_orbit_windows::multiply_u256_tau_frontier15_budget_affine_solinas_gauge_xyzz_tau(\n")
    front_path.write_text(front)
    receipt_path = target / "native-bench-overlay.json"
    receipt = json.loads(receipt_path.read_text())
    receipt.update({
        "variant": "frontier15_budget_affine_solinas_gauge_xyzz_tau",
        "frontier_bench_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_front_sha256": sha256(front_path.read_bytes()).hexdigest(),
    })
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_frontier15_bench.py TARGET_DIR")
    main(Path(sys.argv[1]))
