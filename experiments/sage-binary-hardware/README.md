# Sage binary-curve hardware plans

This package adds reusable fixed-power Frobenius plans for ordinary binary
Koblitz curves over GF(2^m), for degrees 1 through 256. A plan precomputes an
exact GF(2)-linear map for its field modulus and power. The portable C++ path
applies byte lookup/XOR tables; Apple Metal is available when Sage is built
with its framework. Optional CUDA and OpenCL adapters are in the Python
module and require their respective runtimes. `backend='auto'` still selects
Sage because the fastest backend depends on the workload.

The standalone `sage-binary-hardware.patch` applies **after**
[`sage-binary-batch.patch`](../sage-binary-batch/sage-binary-batch.patch) to
Sage 10.10.rc0 commit `671dfa344f4cc4a6d54f343cbfd1272ee81698c9`.
It adds five source files, Meson registration and a manual entry. No local
dependency or build-environment adjustments are included. Apply both patches
to a separate Sage checkout at that revision, then build the checkout with
Sage's normal source-build procedure:

```sh
git -C /path/to/sage apply /path/to/cryptanalysis/experiments/sage-binary-batch/sage-binary-batch.patch
git -C /path/to/sage apply /path/to/cryptanalysis/experiments/sage-binary-hardware/sage-binary-hardware.patch
```

For an installed patched Sage:

```python
from sage.schemes.elliptic_curves.binary_hardware import FrobeniusPlan
F = GF(2**131, 'z')
E = EllipticCurve(F, [1, 1, 0, 0, 1])
# points is a collection of points on E.
with FrobeniusPlan(E, power=65, backend='cpu') as plan:
    images = plan.apply(points)
```

`backend='metal'` uses Apple Metal, when available. The public API returns
ordinary Sage points; `apply_words` exposes the lower-level exact field map.
The lookup tables and dispatch use variable-time research arithmetic.

## Evidence

`run-003/` preserves 22 installed-build cells, each with 12 balanced rounds.
The calls include packing, transfer, Sage-point reconstruction, exact
verification and cleanup. Construction and first call are recorded separately.
The archived comparison is against the older Sage Frobenius path and is
described in [RESULT.md](RESULT.md). The later native path in the preceding
batch PR changes the comparison: the [fresh rebaseline](../sage-ic-campaign/metal-rebaseline-20260924/RESULT.md)
shows that native Sage wins at power 1 while table plans can win at power 65.
Metal did not beat the CPU table plan on those complete API cells.

The recorded source files are in `source/`. `package-manifest.json` binds
them to the patch and retained receipts. Check the archive without Sage:

```sh
python3 experiments/sage-binary-hardware/verify_archive.py
```

For a new Sage installation, run the arithmetic tests. Select `cpu` on any
supported host and add `metal` on a macOS host with Metal access:

```sh
SAGE_BINARY_USE_INSTALLED=1 SAGE_BINARY_BACKENDS=cpu,metal \
  /path/to/sage/sage -python experiments/sage-binary-hardware/test_hardware.py
```

The archived native binary paths and hashes are historical identities. No
machine-specific binary is committed. The portable verifier checks patch
reconstruction and receipt consistency; it cannot reproduce GPU timings on
another machine. This package accelerates one public point-map operation.
It does not establish a complete index-calculus speedup.
