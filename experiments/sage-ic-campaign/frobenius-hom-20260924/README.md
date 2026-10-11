# Native binary squaring for public Frobenius isogeny calls

This directory contains a standalone Sage patch for
`src/sage/schemes/elliptic_curves/hom_frobenius.py`. It is stacked on the
campaign's native binary point-map implementation. The patch accelerates
`EllipticCurveHom_frobenius._call_` for ordinary standard Sage points on
Koblitz curves over NTL binary fields. The general projective evaluation is
retained for other curves, point classes, extension points, zero or
full-field Frobenius powers, and unavailable native backends.

The guard is computed once per isogeny and checks the standard point class
again on every call. That second check matters: the first candidate's cached
guard could still run after a curve's point class changed. Its constructor
count test failed, so the candidate source, timing, and failure log are
archived in `candidate-v1/`, `run-002/`, and `tests-hom-v1.log`. The revised
source, frozen intent, tests, and accepted timing are in `source/` and
`run-003/`.

From the repository root, verify the patch and receipts without Sage:

```sh
python3 experiments/sage-ic-campaign/frobenius-hom-20260924/verify_archive.py
```

Apply `frobenius-hom.patch` from a compatible Sage checkout root. The archived
baseline source hash is fixed in both candidate intents. The local run
installed the exact revised source hash listed in `install-002/install.json`.
See [RESULT.md](RESULT.md) for full API measurements and limitations.
