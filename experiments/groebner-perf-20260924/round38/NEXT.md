# Next measured experiments

## Complete-query compact scheduling

Run two predeclared small trials (31 measured pairs plus one warmup) and two
wide trials (seven pairs plus one warmup), with distinct recorded arm-order
seeds. Keep all previous CPU and GPU arms, including implementations older
than the immediate full-grid baseline. The new auditor compares compact Metal
with the fastest actually executed previous Metal arm in each pair, as well
as the fastest CPU. A CPU fallback cannot count as GPU execution. A per-trial
gate is only one part of repeated qualification, not automatic promotion.

Preserve the unchanged load gate, every rejected admission and every failed
or ineligible attempt. Run no local builds, tests or offline audits during the
timing sequence. Charge the complete fresh query and its independent proof,
equation checks and curve replay. Record setup separately. Inspect kernel time,
host/device wall time, full query time, exact branch counts, map storage and
full-buffer transfer costs. A nearly halved branch count is not a measured
2x query speedup.

## Wider constant elimination

The next isolated GPU change can support up to 55 lifted features while
retaining the current 32-equation limit. That would cover the feature widths
of the 24/27-variable controls, whose requested GPU currently falls back to
CPU. It would move only constant linearization to the device; the expensive
affine-certificate stage would still execute on the CPU.

Use an explicitly versioned output layout for the wider reduced rows and
retain their equation-combination witness. One possible implementation uses
two 32-bit shuffle operations for each 64-bit row, avoiding an assumption
about a native 64-bit shuffle overload. Actual device compilation and exact
tests must establish support. Retain compact/full scheduling, diagonal and
padded groups, both fresh symmetry modes, full equation provenance and CPU
fallback. Compare packing, increased output traffic and complete query costs.
Do not infer an affine-stage speedup from a successful constant-stage port.

## Bounded affine certificates on the GPU

Prototype cooperative elimination for the independent residual systems within
one query. Compare full forward provenance with deferred dependency expansion;
round36 demonstrates that fewer counted word XORs need not reduce wall time.
Preserve pivot order or independently prove equivalent complete identities.
Bound row generation, reductions, reconstruction, workspace and proof output.
Record every budget exhaustion and charge exact CPU fallback to the same query.

Choose groups per threadgroup using measured register pressure and actual
device memory limits. The coefficient and dependency matrices can dominate
per-group storage. Build separate native binaries for any new hardware;
physical Metal correctness does not establish CUDA/OpenCL support or speed.

## F6 research and the full pipeline

The [research protocol](../round35/NEXT.md) covers symbolic elimination,
separators, rank-changing updates and established Polynomial XL/Crossbred
baselines. The current wide original-ANF polynomial-support graphs are complete,
so direct small-separator elimination has no demonstrated advantage on these
encodings. A reformulation needs its own charged experiment and exceptional
specialization checks; Boolean polynomial coefficients can be zero divisors.

An asymptotic result needs a named family, proved applicability and bounds
including proof checking. Constant scheduling/code-generation improvements
do not supply that result. After component gains, freeze the complete IC
candidate and workload and measure one new public target through verified
scalar recovery against rho on the same point and resources. These planted
PDP controls keep candidate/IC/rho fields null.
