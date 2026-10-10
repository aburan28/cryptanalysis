#!/usr/bin/env python3
"""Count selected mixed additions from the saved atlases and scalar law."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
source = HERE.parent / "prime-j0-tau-power16-20261010" / "screen.py"
spec = importlib.util.spec_from_file_location("tau_power16_screen", source)
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)


def load_atlas(path):
    raw = path.read_bytes()
    assert raw[:3] == b"T2B"
    width = raw[3] - ord("0")
    count = struct.unpack_from("<I", raw, 4)[0]
    radix = 1 << width
    code_start = 8
    seed_start = code_start + 4 * radix * radix
    assert len(raw) == seed_start + 4 * count
    seeds = [struct.unpack_from("<hh", raw, seed_start + 4 * i)
             for i in range(count)]
    return raw, radix, seeds, code_start


def count(scalar, schedule):
    a, b = screen.representative(scalar % screen.ORDER)
    selected = 0
    for raw, radix, seeds, code_start in schedule:
        slot = (a % radix) * radix + b % radix
        code = struct.unpack_from("<I", raw, code_start + 4 * slot)[0]
        digit, _ = screen.digit_from_code(code, seeds)
        assert (digit[0] % radix, digit[1] % radix) == (a % radix, b % radix)
        a = (a - digit[0]) // radix
        b = (b - digit[1]) // radix
        selected += (code >> 4) != 0
    assert (a, b) == (0, 0)
    return max(0, selected - 1)


def panel(label, input_path, modes):
    inputs = json.loads(input_path.read_bytes())
    scalars = [int(text, 16) for text in inputs["scalars_hex"]]
    result = {}
    for name, schedule in modes.items():
        counts = [count(scalar, schedule) for scalar in scalars]
        result[name] = {"total_mixed_additions": sum(counts),
                        "histogram": dict(sorted(Counter(counts).items()))}
    return {"input_sha256": sha256(input_path.read_bytes()).hexdigest(),
            "count": len(scalars), "modes": result}


def main():
    full8 = load_atlas(HERE.parent / "prime-j0-tau-frontier-20261010/w8-d256/atlas-w8.bin")
    final9 = load_atlas(HERE.parent / "prime-j0-tau-power16-20261010/atlas-w9.bin")
    full9 = load_atlas(HERE / "atlas-w9.bin")
    modes = {"frontier15_bound_budget": [full8] * 6 + [full9] * 8 + [final9],
             "frontier16_beta_solinas": [full8] * 15 + [final9]}
    prior = panel("prior", HERE.parent / "prime-j0-frontier16-compact-affine-20261010/fresh-inputs.json", modes)
    assert prior["modes"]["frontier15_bound_budget"]["total_mixed_additions"] == 57_344
    assert prior["modes"]["frontier16_beta_solinas"]["total_mixed_additions"] == 61_439
    fresh = panel("fresh", HERE / "fresh-inputs.json", modes)
    record = {"schema": 1,
              "atlas_sha256": {"full8": sha256(full8[0]).hexdigest(),
                               "full9": sha256(full9[0]).hexdigest(),
                               "final9": sha256(final9[0]).hexdigest()},
              "prior": prior, "fresh": fresh}
    target = HERE / "operation-counts.json"
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"fresh": fresh["modes"], "prior": prior["modes"]}, sort_keys=True))


if __name__ == "__main__":
    main()
