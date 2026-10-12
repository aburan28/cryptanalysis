#!/usr/bin/env python3
"""Replay the frozen priority atlas on the direct-rho scalar panel."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-dual-orbit-20261011"
SPEC = importlib.util.spec_from_file_location("direct_rho_priority_screen",
                                             PARENT / "priority_screen.py")
priority = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(priority)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    cover = PARENT / "cover-priority-rho0.bin"
    raw = cover.read_bytes()
    magic, radix, classes, seeds, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, seeds, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 0b1111)
    words = struct.unpack_from(f"<{classes}I", raw, 20)
    assignment = [(word >> 4, word & 15) for word in words]
    seed_offset = 20 + 4 * classes
    seed_points = list(struct.iter_unpack("<hh", raw[seed_offset:]))
    assert len(seed_points) == seeds
    canonical, nodes, _, _ = priority.base.parent.full_classes()
    priority.base.PANEL = HERE / "fresh-inputs.json"
    panel = priority.base.replay_panel(assignment, seed_points, nodes, canonical)
    assert panel["terminal_bound_failures"] == 0
    receipt = {"schema": 1, "status": "passed", "panel": panel,
               "cover_sha256": digest(cover),
               "input_sha256": digest(priority.base.PANEL),
               "replayer_sha256": digest(Path(__file__))}
    (HERE / "fresh-replay.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(panel, sort_keys=True))


if __name__ == "__main__":
    main()
