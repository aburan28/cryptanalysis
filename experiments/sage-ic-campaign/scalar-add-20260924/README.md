# Sage finite-field point addition

This directory packages an incremental two-file Sage patch on top of PR #79.
For standard finite-field points on the supported binary Weierstrass model,
`EllipticCurvePoint_field._add_` calls the already verified native batch
addition for one pair. Its general formula now reuses the `x1 == x2`
comparison. Standard finite-field outputs from that formula are initialized
by a small Cython helper with the correct C-level `Element._parent`; custom
point classes and installations without the optional extension retain the
ordinary Sage constructor.

The experiment kept three unsuccessful candidates. A class-level guard
regressed prime and unsupported-model calls. Moving the branch into the
existing method still regressed those controls. A Python-only direct point
constructor then failed equality because assigning `_parent` from Python
did not initialize Sage's C-level parent. Those source snapshots, timings,
and failure logs are retained; each held version is reconstructed from its
small `held-v*.patch` and frozen hash. The accepted source is in `source/`, with
paired results in `run-005/`.

Run this portable audit from the repository root:

```sh
python3 experiments/sage-ic-campaign/scalar-add-20260924/verify_archive.py
```

Apply `scalar-add.patch` with `git apply --unidiff-zero` from a compatible
Sage checkout root, rebuild
`binary_batch_ntl`, and install both modified files together. The exact
source and installed binary hashes are in `install-004/install.json`.
See [RESULT.md](RESULT.md) for measurements and limits.
