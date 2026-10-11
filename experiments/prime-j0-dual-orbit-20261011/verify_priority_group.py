#!/usr/bin/env python3
"""Replay priority assigned points on the frozen design scalar panel."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "priority_group_reference", HERE / "verify_group.py")
group = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(group)


class Atlas(group.Atlas):
    def __init__(self, nodes, canonical):
        path = HERE / "cover-priority-rho0.bin"
        raw = path.read_bytes()
        magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
        assert (magic, radix, classes, count, mask) == \
            (b"LP21", 1024, len(nodes), 67_338, 0b1111)
        self.name = "priority_rho0"
        self.digest = sha256(raw).hexdigest()
        self.mask = mask
        self.nodes = nodes
        self.canonical = canonical
        self.node_index = {node: index for index, node in enumerate(nodes)}
        self.codes = memoryview(raw)[20:20 + 4 * classes]
        self.seeds = list(struct.iter_unpack("<hh", raw[20 + 4 * classes:]))
        assert len(self.seeds) == count and self.seeds[0] == (0, 0)


def main():
    canonical, nodes, _, _ = group.cover.parent.full_classes()
    panel = json.loads(group.PANEL.read_bytes())
    scalars = [int(value, 16) for value in panel["scalars_hex"][:group.LIMIT]]
    assert len(scalars) == group.LIMIT
    bases = []
    base = group.curve.G
    for _ in range(13):
        bases.append((base, group.curve.tau_point(base)))
        base = group.curve.multiply(1024, base)
    atlas = Atlas(nodes, canonical)
    result = group.replay(atlas, scalars, bases)
    previous = json.loads((HERE / "group-screen.json").read_bytes())
    assert result["output_sha256"] == \
        previous["results"]["rho0"]["output_sha256"]
    receipt = {"schema": 1, "status": "passed",
               "purpose": "design_point_replay", "atlas_sha256": atlas.digest,
               "panel_sha256": sha256(group.PANEL.read_bytes()).hexdigest(),
               "verifier_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "result": result}
    (HERE / "priority-group-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
