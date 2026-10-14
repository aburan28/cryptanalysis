#!/usr/bin/env python3
"""Move fixed-gauge rotation to the window bases before table construction."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def once(body, old, new):
    assert body.count(old) == 1, old[:100]
    return body.replace(old, new, 1)


def first(body, old, new):
    assert old in body, old[:100]
    return body.replace(old, new, 1)


def main(target):
    spec = importlib.util.spec_from_file_location("mixed640_gauge_overlay", HERE / "native_gauge128.py")
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    overlay.main(target)
    source = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    body = source.read_text()
    marker = "// Inserted into the pinned mixed-radix 640 module by native_overlay.py."
    before, variant = body.split(marker, 1)
    variant = first(variant,
        "            let plain = build_u256_window(&seeds, base);\n"
        "            let tau = build_u256_window(&seeds, base.tau());",
        "            let plain_base = match MIXED640_GAUGES[index][0] {\n"
        "                0 => base, 1 => base.omega(), 2 => base.omega().omega(),\n"
        "                _ => unreachable!(),\n"
        "            };\n"
        "            let tau_base = base.tau();\n"
        "            let tau_base = match MIXED640_GAUGES[index][1] {\n"
        "                0 => tau_base, 1 => tau_base.omega(),\n"
        "                2 => tau_base.omega().omega(), _ => unreachable!(),\n"
        "            };\n"
        "            let plain = build_u256_window(&seeds, plain_base);\n"
        "            let tau = build_u256_window(&seeds, tau_base);")
    variant = first(variant,
        "                    plain: plain.unit_solinas(2 * MIXED640_GAUGES[index][0]),\n"
        "                    tau: tau.unit_solinas(2 * MIXED640_GAUGES[index][1]),",
        "                    plain,\n"
        "                    tau,")
    variant = variant.replace("mixed640_gauge128_retained_bytes",
                              "mixed640_gaugebase128_retained_bytes")
    source.write_text(before + marker + variant)
    gauges = json.loads((HERE / "gauge-policy.json").read_text())["gauges"]
    slots = [21847] * 6 + [34135] * 7 + [45163]
    receipt = {
        "schema": 1,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy_sha256": sha256((HERE / "gauge-policy.json").read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(source.read_bytes()).hexdigest(),
        "removed_per_entry_solinas_rotations": sum(
            n * sum(g != 0 for g in row) for n, row in zip(slots, gauges)),
        "window_base_omega_calls": sum(sum(row) for row in gauges),
        "point_and_atlas_bytes": 415190 * 128 + 4729980,
    }
    (target / "native-gauge128-base-overlay.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]).resolve())
