# Batched affine half-trace S3 inverse on the exact N131 source

Factoring the S3 quadratic's half-trace into a reusable source term and a
target term reduces the complete **8,176-output** fixed-seed join to **one
field inversion and one half-trace per target coordinate**, plus linear
field multiplication and lookup work. All three frozen N131 queries agree
with an independent Sage root oracle at **every** left output; the
constructed four-atom case has its archived, independently group-replayed
coordinate hit, and both admissible raw lifts of the published challenge
point have zero hits in this fixed two-pair family. A linear exceptional
case and a trace-mismatch case also pass full-domain replay.

This kernel operates on `EC1N131Ckb1heb5f1998f20b` over
`GF(2)[t]/(t^131+t^13+t^2+t+1)`, using the exact W15 pair-output sets
for mask-XOR seeds `12004` and `9022` at rotations `0` and `13`. The
left and right sets contain 8,176 and 8,340 distinct reciprocal output
coordinates. The [frozen protocol](protocol.json) binds the source, complete
pair-root file, checked Sage runtime, prior independently audited results,
one worker, and 120-second/4-GiB per-coordinate limits. This is a stage
kernel for a future target-coupled relation generator; its candidate ID
remains `null` until a complete IC pipeline is specified.

## Algebra and work reduction

For left pair output `c`, right pair output `d`, and supplied target
reciprocal `q`, the S3 equation is

`(c+d+q)^2 + cdq + (cdq)^2 = 0`.

Writing `alpha=(1+cq)^2`, `beta=cq`, and `gamma=(c+q)^2`, its quadratic
form in `d` is `alpha*d^2+beta*d+gamma=0`. When `cq != 1`, the usual
half-trace argument simplifies exactly:

`alpha*gamma/beta^2 = (c+1/c+q+1/q)^2`.

For odd field degree, let `H(v)=sum_(j=0)^65 v^(2^(2j))`; then
`H(v)^2+H(v)=v+Tr(v)`. The reusable preparation stores
`h(c)=H((c+1/c)^2)` and `tau(c)=Tr((c+1/c)^2)` for each left output.
The target computes `h(q)` and `tau(q)` once. If their trace bits agree,
the two possible right outputs are

`d_epsilon = cq/(1+cq)^2 * (h(c)+h(q)+epsilon)`, `epsilon in {0,1}`.

One Montgomery batch inversion covers `q` and every nonzero `1+cq` in
the same target query. At `cq=1`, the equation is linear and gives
`d=(c+q)^2`; the implementation handles this before the trace filter.
The previous [Sage oracle](../n131_w15_fixedseed_s3_join_20261010/sage_audit.py)
formed two field divisions and one half-trace for every left output in
the ordinary quadratic branch. The new query uses one field inversion
and one half-trace for the whole 8,176-output scan, with linear field
multiplications. Preparation is target independent: it uses one batched
inversion and 8,176 half-traces and is recorded separately.

## Frozen measurements and checks

The checked Sage launcher recorded [runtime information](sage_runtime_info.json)
before execution. Reusable setup took **1.054392 s** and reached
246,071,296 bytes process high-water RSS. The final frozen run gave:

| Supplied reciprocal coordinate | Complete left outputs | New target query | Independent full-root replay | Coordinate hits |
| --- | ---: | ---: | ---: | ---: |
| Constructed four-atom control | 8,176 | 0.129674 s | 13.774509 s | 1 |
| Published point, raw lift 0 | 8,176 | 0.029456 s | 15.988289 s | 0 |
| Published point, raw lift 2 | 8,176 | 0.179204 s | 25.592433 s | 0 |

The target-query interval begins with `q` supplied and source transforms
ready. It ends after batch inversion, all S3 roots, and right-set lookup.
The independent replay calls the earlier Sage quadratic oracle on every
left output **outside** that interval and compares the complete root set,
not just hits. Each query reached `COMPLETE` within its cap and used one
batch inversion. The largest process high-water RSS was 254,296,064 bytes.
The controls additionally checked the unique `cq=1` linear case and a
`q=2` trace-mismatch case against every oracle root. The
[result receipt](result.json) preserves all phase intervals, statuses,
hits, edge controls, and input hashes; the read-only
[archive audit](audit_archive.py) checks those bindings. CPU wall times
are algorithmic diagnostics on an unisolated host; the algebraic
operation-count reduction and complete root agreement are exact.

The next gate is a **target-coupled five-pair membership and witness
generator** that supplies useful four-atom residuals before this kernel
runs. The exact W15 [prefix-support bound](../n131_w15_prefix_support_gate_20261010/RESULT.md)
requires capacity for at least 7,914 distinct target-independent one-pair
prefixes within 600 seconds for a 50% union-bound success ceiling. This
fixed-seed two-pair join supplies a fast terminal predicate, while a joint
generator must still eliminate the other free pair blocks and count
ordinary relations and novel rank on the public point. Any N131 CPU
performance claim also requires an isolated benchmark receipt.

Reproduce the result in a fresh repository copy by saving
`./sage --runtime-info` to this experiment's `sage_runtime_info.json`, then
running its `run.py freeze` and `run.py run` modes through `./sage -python`.
The archived run is immutable. `python3 -B audit_archive.py` from this
directory rechecks the committed receipt without rerunning Sage.
