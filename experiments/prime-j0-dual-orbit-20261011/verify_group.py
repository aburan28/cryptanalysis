#!/usr/bin/env python3
"""Point-replay the low-cost degree-seven orbit buckets."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REFDIR = ROOT / "prime-j0-tau-power16-20261010"
sys.path.insert(0, str(REFDIR))
REFSPEC = importlib.util.spec_from_file_location("dual_bucket_curve", REFDIR / "verify_group.py")
curve = importlib.util.module_from_spec(REFSPEC)
REFSPEC.loader.exec_module(curve)
sys.path.pop(0)
BASESPEC = importlib.util.spec_from_file_location("dual_bucket_cover", HERE / "screen.py")
cover = importlib.util.module_from_spec(BASESPEC)
BASESPEC.loader.exec_module(cover)
PANEL = ROOT / "prime-j0-adic-orbit-20261011/fresh-inputs.json"
MODES = ("rho0", "rho0_bar0")
LIMIT = 256


def digest(raw):
    return sha256(raw).hexdigest()


class Atlas:
    def __init__(self, name, nodes, canonical):
        path = HERE / f"cover-lowcost-{name}.bin"
        raw = path.read_bytes()
        magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
        assert (magic, radix, classes) == (b"LC19", 1024, len(nodes))
        self.name = name
        self.digest = digest(raw)
        self.mask = mask
        self.nodes = nodes
        self.canonical = canonical
        self.node_index = {node: index for index, node in enumerate(nodes)}
        self.codes = memoryview(raw)[20:20 + 4 * classes]
        self.seeds = list(struct.iter_unpack("<hh", raw[20 + 4 * classes:]))
        assert len(self.seeds) == count and self.seeds[0] == (0, 0)

    def decode(self, a, b):
        ra, rb = a % 1024, b % 1024
        node = self.canonical[ra * 1024 + rb]
        index = self.node_index[node]
        code = struct.unpack_from("<I", self.codes, 4 * index)[0]
        seed_id, map_id = code >> 4, code & 15
        assert self.mask & (1 << map_id) and seed_id < len(self.seeds)
        mapped = cover.mapped(self.seeds[seed_id], map_id)
        options = [(unit, digit) for unit, digit in enumerate(cover.screen.units(mapped))
                   if digit[0] % 1024 == ra and digit[1] % 1024 == rb]
        assert options
        unit, digit = options[0]
        assert cover.screen.norm(digit) <= 1024 * 1024
        return digit, seed_id, map_id, unit


def rho_point(point):
    return curve.add(point, curve.tau_point(point))


def rho_bar_point(point):
    return curve.add(curve.multiply(4, point), curve.negate(curve.tau_point(point)))


def point_bytes(point):
    return bytes(64) if point is None else \
        point[0].to_bytes(32, "big") + point[1].to_bytes(32, "big")


def replay(atlas, scalars, bases):
    cached = {}
    operations = Counter()
    output_hash = sha256()
    terminal_maximum = 0
    for scalar in scalars:
        a, b = cover.screen.representative(scalar % cover.screen.ORDER)
        assert (a + b * curve.LAMBDA_TAU - scalar) % cover.screen.ORDER == 0
        start = a, b
        place = 1
        reconstruction = [0, 0]
        buckets = {}
        for row in range(12):
            digit, seed_id, map_id, unit = atlas.decode(a, b)
            reconstruction[0] += place * digit[0]
            reconstruction[1] += place * digit[1]
            if seed_id:
                key = row, seed_id
                if key not in cached:
                    sa, sb = atlas.seeds[seed_id]
                    base, tau_base = bases[row]
                    cached[key] = curve.add(curve.multiply(sa, base),
                                            curve.multiply(sb, tau_base))
                point = curve.unit_point(cached[key], unit)
                branch, exponent = divmod(map_id, 3)
                bucket_key = branch, exponent
                old = buckets.get(bucket_key)
                if old is not None:
                    operations["bucket_additions"] += 1
                buckets[bucket_key] = curve.add(old, point)
                operations["nonzero_full_digits"] += 1
            assert (a - digit[0]) % 1024 == (b - digit[1]) % 1024 == 0
            a, b = (a - digit[0]) // 1024, (b - digit[1]) // 1024
            place *= 1024
        terminal_norm = cover.screen.norm((a, b))
        assert terminal_norm < 149 * 149
        terminal_maximum = max(terminal_maximum, terminal_norm)
        reconstruction[0] += place * a
        reconstruction[1] += place * b
        assert tuple(reconstruction) == start
        if a or b:
            base, tau_base = bases[12]
            terminal = curve.add(curve.multiply(a, base),
                                 curve.multiply(b, tau_base))
            old = buckets.get((0, 0))
            if old is not None:
                operations["bucket_additions"] += 1
            buckets[(0, 0)] = curve.add(old, terminal)
            operations["nonzero_terminal_digits"] += 1

        aggregate = None
        for branch in range(3):
            branch_sum = None
            for exponent in range(3):
                term = buckets.get((branch, exponent))
                if term is None:
                    continue
                for _ in range(exponent):
                    term = curve.tau_point(term)
                    operations["outer_tau_maps"] += 1
                if branch_sum is not None:
                    operations["branch_additions"] += 1
                branch_sum = curve.add(branch_sum, term)
            if branch_sum is None:
                continue
            if branch == 1:
                branch_sum = rho_point(branch_sum)
                operations["rho_maps"] += 1
            elif branch == 2:
                branch_sum = rho_bar_point(branch_sum)
                operations["rho_bar_maps"] += 1
            if aggregate is not None:
                operations["branch_merges"] += 1
            aggregate = curve.add(aggregate, branch_sum)
        expected = curve.multiply(scalar % cover.screen.ORDER, curve.G)
        assert aggregate == expected, (atlas.name, scalar)
        output_hash.update(point_bytes(aggregate))
    return {"cases": len(scalars), "output_sha256": output_hash.hexdigest(),
            "cached_seed_points": len(cached),
            "terminal_maximum_norm": terminal_maximum,
            "operations": dict(sorted(operations.items()))}


def main():
    canonical, nodes, _, _ = cover.parent.full_classes()
    panel = json.loads(PANEL.read_bytes())
    scalars = [int(value, 16) for value in panel["scalars_hex"][:LIMIT]]
    assert len(scalars) == LIMIT
    bases = []
    base = curve.G
    for _ in range(13):
        bases.append((base, curve.tau_point(base)))
        base = curve.multiply(1024, base)
    results = {}
    atlases = {}
    for name in MODES:
        atlas = Atlas(name, nodes, canonical)
        atlases[name] = atlas.digest
        results[name] = replay(atlas, scalars, bases)
    assert len({result["output_sha256"] for result in results.values()}) == 1
    receipt = {"schema": 1, "status": "passed", "purpose": "design_point_replay",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "cover_source_sha256": digest((HERE / "screen.py").read_bytes()),
               "curve_source_sha256": digest((REFDIR / "verify_group.py").read_bytes()),
               "panel_sha256": digest(PANEL.read_bytes()),
               "atlas_sha256": atlases, "results": results}
    (HERE / "group-screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
