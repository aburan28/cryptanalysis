# Q1426 v1 producer failure

The first frozen source (`7c54382b9`) failed in `test_slice.py` before
any SAT formula construction. Its `run.py` imported Q1425's file under
the generic module name `run`, which resolved to Q1426's own module when
the control imported Q1426 first. `check_freeze()` then raised
`AttributeError: module 'run' has no attribute 'digest'`.

No solver call or timing result was produced. The original freeze is
preserved here. V2 loads Q1425 under a distinct module name and is
refrozen before measurement.
