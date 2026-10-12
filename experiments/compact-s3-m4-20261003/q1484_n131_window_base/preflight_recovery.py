#!/usr/bin/env python3
"""Check Q1484 R2 ordinal replay against R1 status and direct group law."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1481 = PARENT / "q1481_window_orbit_base"
R1 = HERE / "runs" / "r1"
sys.path.insert(0, str(PARENT))
from enumerate_q1413_projected_x import projected_x  # noqa: E402
from run_probe import curves, field  # noqa: E402
sys.path.insert(0, str(Q1481))
from enumerate_base import OrbitKey, onb_x_from_cycle_mask  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mask_for(index: int) -> tuple[int, int]:
    if index == 0:
        return 1, 1
    span = index.bit_length() + 1
    interior = index - (1 << (span - 2))
    assert 0 <= interior < 1 << (span - 2)
    return 1 | (1 << (span - 1)) | (interior << 1), span


def main() -> None:
    failure = json.loads((R1 / "failure.json").read_text())
    prefix = failure["durable_checkpoint_processed_raw_x_orbits"]
    flags = (R1 / "status_flags.partial").read_bytes()
    assert len(flags) * 4 == prefix
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    sample = set(range(4096))
    sample.update({prefix - 1, prefix - 2, prefix // 2,
                   (1 << 25) - 1 if prefix > (1 << 25) else prefix - 1024})
    for index in range(256):
        digest = hashlib.sha256(f"Q1484R2-{index}".encode()).digest()
        sample.add(int.from_bytes(digest, "little") % prefix)
    direct_group_checks = rational_checks = 0
    for index in sorted(sample):
        mask, span = mask_for(index)
        assert 1 <= span <= 27
        x = onb_x_from_cycle_mask(mask, onb, orbit)
        rational, projected = projected_x(onb, x)
        code = 0 if not rational else 1 if projected is None else 2
        old_code = (flags[index >> 2] >> ((index & 3) << 1)) & 3
        assert code == old_code, index
        if direct_group_checks < 64 and (rational or index < 16):
            point = curve.pointFromX(x)
            assert (point is not None) == rational
            image = curve.mul(point, 4) if point is not None else None
            assert (image[0] if image is not None else None) == projected
            direct_group_checks += 1
            rational_checks += int(rational)
    result = {
        "kind": "q1484_r2_checkpoint_replay_preflight",
        "proposal_id": "Q1484", "attempt_id": "Q1484R2",
        "status": "PASS", "degree_n": 131,
        "r1_prefix_raw_orbits": prefix,
        "sampled_status_checks": len(sample),
        "direct_group_law_checks": direct_group_checks,
        "direct_group_law_rational_checks": rational_checks,
        "r1_failure_sha256": sha(R1 / "failure.json"),
        "r1_partial_bitmap_sha256": sha(R1 / "status_flags.partial"),
        "r2_enumerator_source_sha256": sha(HERE / "enumerate_n131_r2.py"),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "r2_sage_runtime_info.json"),
    }
    output = HERE / "r2_preflight.json"
    assert not output.exists(), "refuse overwrite"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
