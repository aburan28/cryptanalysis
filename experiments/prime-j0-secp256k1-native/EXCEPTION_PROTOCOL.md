# Cached Jacobian exceptional-addition control

Freeze the native source, this protocol, and `run_exception_controls.py`
before executing the control. For the secp256k1 generator and its
double and triple, represent each operand with several nonzero
projective scales. Check that cached
addition of the point to itself equals independent Jacobian doubling,
and that cached addition to its negation returns the identity. The
code must report the exceptional branch separately; generic cached
addition operation counts do not describe that branch.

Build the offline locked release binary and run its
`--check-exceptions` control. Then rerun the frozen
original 64, edge 30, and held-out 256 scalar-input fixtures. Retain
raw control/build/replay exits and source/fixture/binary hashes. For these
350 nonexceptional fixture inputs, the exceptional count must be zero,
all native representative/digit/seed/output checks must still pass,
and previously recorded generic operation counts must be unchanged.

This control covers the equal-X cached-add cases but is not a
constant-time or CPU-speed claim. It does not establish secret-scalar
safety or general validation of arbitrary, potentially invalid points.
