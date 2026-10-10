# Q20261010111900: sparse-quadratic fixed-output S3 root kernel

This experiment measures an arithmetic improvement to the complete
fixed-output right-pair scan in Q20261010103500. It keeps the same exact
curves, factor bases, four frozen outputs, workload IDs, mask domains,
two inversion windows, and 120-second/512-MiB cell caps. Its new Rust
binary, input manifests, and build receipt are frozen before measurement.
The proposal ID is `Q20261010111900`; candidate and run IDs remain null,
and `isogeny` is `"none"` (`ISO0`). The measured stage is point
decomposition, not final relation-matrix linear algebra.

For fixed output `v` and first-leaf x mask `x`, write
`a=(x+v)^2`, `p=xv`, `s=p^2`, and `D=as`. The nondegenerate S3 equation
in the second leaf y is `a y^2 + p y + s + 1 = 0`. Its two roots are
`q*HT(d)` and `q*HT(d)+q`, where `q=(ps)/D`,
`d=a^2(s+1)/D`, and `HT` is the odd-degree half-trace. Here `a`, `p`, and
`s` are affine or linear functions of the Boolean bits in `x`, while
`D=as`, `ps`, and `a^2(s+1)` are quadratic. For a basis image `e_i`, the kernel
precomputes their one-bit coefficients and, for every `i<j`, the
two-bit cross products. Enumerating a weight-at-most-`w` mask then
requires at most `w` one-bit and `w(w-1)/2` two-bit XOR table entries
for each quadratic expression. Montgomery inversion batching remains
the same; the regular root needs a field multiplication for `d`, then
two more only when its trace permits roots. The `x=v` case retains its
exact linear S3 branch.

The target-dependent quadratic precompute is inside the scan timing
and operation counts. A field multiplication used during precompute or
batch inversion is charged once in its actual phase. The binary records
all root calls, field multiplications, inversions, basis conversions,
wall time, peak RSS, and weight-pair hits. The known-solution controls
must reproduce the same independently checked four-point relations
as Q20261010103500. The first ordinary fixed output at each degree
must reproduce its complete zero-pair decision. An exhaustive
degree-five field test compares every nonzero output and every
nonzero first-leaf mask against the independent direct S3 root formula.

N53 uses `EC1N53Ckb1hf77aab617904`, Q1301 W≤3, B=24,062,
K=227, and 24,857 raw masks. N83 uses
`EC1N83Ckb1h876c2921cb64`, Q1325 W≤5, B=30,977,592,
K=186,612, and 30,967,383 raw masks. B counts actual subgroup-usable
points before folding; K counts signed-Frobenius columns. Each input
manifest retains the exact enumerated-set digest and hashed workload.
The matched comparison is by curve, base, target, output, and batch
window, with separate field-operation and wall-time evidence. CPU
wall-time ratios remain exploratory without a host-isolation receipt.

The N131 comparison uses the exact W≤6 base B/K and retains separate
uniform-query and uniform-fixed-output conditions. It charges the
measured root-kernel operation ratio only as an extrapolation. The
fully charged cold and one-target online N131 exponents stay null
until natural relation yield, novel rank, final matrix work, target
descent, and scalar replay have one common accounting unit.
