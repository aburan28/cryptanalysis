"""Exact, small checks of the installed Sage binary-curve release stack."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl, binary_hardware
from sage.schemes.elliptic_curves.binary_hardware import FrobeniusPlan
from sage.schemes.elliptic_curves import ell_point, hom_frobenius


root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "scripts" / "sage-release-manifest.json").read_text())
installed = {
    "binary_batch.py": binary_batch.__file__,
    "binary_hardware.py": binary_hardware.__file__,
    "ell_point.py": ell_point.__file__,
    "hom_frobenius.py": hom_frobenius.__file__,
}
for filename, path in installed.items():
    expected = manifest["files"]["src/sage/schemes/elliptic_curves/" + filename]
    actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    assert actual == expected, f"installed {filename} differs from release source"

F = GF(2**7, "z", impl="ntl")
E = EllipticCurve(F, [1, 1, 0, 0, 1])
P, Q = E.random_point(), E.random_point()
assert binary_batch_ntl.supports(F)
assert binary_batch.add_pairs(E, [(P, Q), (P, -P), (E(0), Q)]) == [P + Q, E(0), Q]
assert binary_batch.add_cartesian(E, [P, Q], [P, Q]) == [P + P, P + Q, Q + P, Q + Q]
points = [E(0), P, Q, P + Q]
reference = [E.frobenius_isogeny(3)(R) for R in points]
assert binary_batch.frobenius_points(E, points, 3) == reference
assert [E.frobenius_isogeny(3)(R) for R in points] == reference
with FrobeniusPlan(E, power=3, backend="cpu") as plan:
    assert plan.apply(points) == reference
    assert plan.apply_batches([points[:2], [], points[2:]]) == [reference[:2], [], reference[2:]]
print("Sage release binary-curve smoke passed")
