# Native singleton binary Frobenius path

This is an incremental Sage patch on top of the public Frobenius-isogeny
fast path in PR #78. It adds `binary_batch_ntl._frobenius_one` and calls it
from the same guarded `EllipticCurveHom_frobenius._call_` branch. The new
native entry point restores the curve's NTL field context **before** it
reads point coordinates. The existing batch routine consumes arbitrary
iterables before restoring context, so using that routine's prepared-input
interface directly from Python is unsafe across field switches.

The initial direct-prepared candidate looked faster on same-field cells,
then failed the cross-field correctness suite. Its frozen intent, source,
profile, and failure log are archived. The revised candidate has two
source files, exact source and installed-binary hashes, new confirmation
seeds, the native context-switch suite, public point tests, and doctests.

To audit the incremental patch and receipts without Sage, run from the
repository root:

```sh
python3 experiments/sage-ic-campaign/frobenius-singleton-20260924/verify_archive.py
```

Apply `native-singleton.patch` from the matching Sage checkout root, rebuild
`binary_batch_ntl`, and install both changed files together. The exact
archived measurements are in `run-002/`; see [RESULT.md](RESULT.md).
