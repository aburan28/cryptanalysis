# Local ONB Frobenius byte tables

This archive accompanies a direct optimization of
`ecc2k130/codegen/field.py:Onb.frob`, the Python ONB field used by the local
elliptic-curve index-calculus reference runner. It is separate from the Sage
patches in the preceding PR stack. The implementation lazily builds a
per-byte index-permutation table for each used Frobenius exponent and then
applies that table to the low `2m+1` bits of each field element.

`baseline/field.py` is the frozen original. `field-v1.py` through
`field-v4.py` preserve held variants; the accepted source is the tracked
`ecc2k130/codegen/field.py`. The cache holds only the two exponent residues
used by the hot IC calls; other exponents use the original loop. Each intent
file was frozen before its timing.

From the repository root, run:

```sh
python3 experiments/sage-ic-campaign/onb-frobenius-20260924/verify_archive.py
```

The verifier checks source hashes, exact arithmetic, recorded gates, and
portable curve-point outputs. Re-run `benchmark.py`, `point_recovery_portable.py`,
or `measure_cold.py` to obtain timings for another machine. The local
`point_recovery.py` run used an untracked audit runner and is retained as a
diagnostic; the portable point-recovery result is the reproducible claim.

The full IC runner requires `pysat` / CryptoMiniSat, unavailable in this local
Python environment. See `RESULT.md` for the measured scope and limits.
