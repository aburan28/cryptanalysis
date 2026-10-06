# PR archive notes

`native-frobenius.patch` is the incremental change on top of the earlier Sage
batch package. The updated standalone Sage patch and complete candidate source
files are in `../sage-binary-batch/`. Machine-specific `.so` files are omitted
from Git; `package-manifest.json` records their measured hashes.

`verify_archive.py` checks the patch, source bindings, balanced timing rounds,
counts, suite calculations, and packaged text hashes without requiring Sage.
It does not rerun the mathematical tests or benchmark. The original
`evidence-manifest.json` retains historical absolute paths from the measured
local runtime; it is preserved as recorded and is distinct from the portable
`package-manifest.json`.
