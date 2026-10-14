# Full-subgroup binary elliptic / genus-two campaign

Preregistered 2026-10-14, before generating the campaign targets. Requested
workload: full-subgroup solves, with a longer compute campaign. No interval
restriction, planted-small-log replacement, or reduction of m=83 is permitted.

## Workloads and hypothesis

Use the two fixtures and the exact degree-three pullback established in
`research/binary_genus2_cover_20261014/REPORT.md`. Field polynomial:
z^83+z^45+z²+z+1. E_a: y²+xy=x³+a*x²+1, a=0 and a=1.
Subgroup orders are respectively 2417851639230796216685689 and
8569786107849059. Generators are the pinned `n83_fixture` generators.
The target C_a is v²+u²v=u⁵+a*u⁴+u³+u. Searches concern only the
injective elliptic pullback image in Jac(C_a), not the whole Jacobian.

The transfer is an isomorphism on this subgroup. An efficient image solver
can invert it and use the same elliptic algorithm. A native Cantor-arithmetic
search may cost more in this implementation; neither outcome establishes an
improved ECDLP algorithm or a security claim.

Generate eight independent, uniformly distributed nonzero targets per a using
OS randomness with rejection sampling. Write only public coordinates, group
parameters and public walk seeds to solver inputs. Keep scalar witnesses in a
separate local file outside all solver input directories. The solver accepts
no witness or interval argument. A separate verifier checks any recovered log
in both the elliptic group and the Jacobian.

## Arms and accounting

1. Direct elliptic signed-Frobenius distinguished-point rho.
2. Jacobian image: inverse the public divisors to E, solve with the same
   elliptic path, then verify the recovered scalar on the original divisors.
3. Native Jacobian addition with signed-Frobenius canonicalization. Every
   search addition is checked Cantor arithmetic; any transfer used to select
   a canonical representative is included and counted explicitly.

Use public deterministic jump/start seeds. Apply all 166 signed Frobenius
automorphisms, track the linear-combination coefficients modulo the complete
prime order, detect/escape short cycles, and use distinguished points with
explicit parameters. Preserve the entire collision table, current walks,
start-stream position, counters and input identity in atomic checkpoints.
Reloading must reproduce an uninterrupted search. No discarded-table restart
may be called a resume. A checkpoint quantum is a scheduling boundary, not a
restriction of the scalar space or an overall campaign stop cap.

Count setup, transfer, search, collision processing, failed collisions,
canonicalizations, native additions, table operations, checkpoint I/O and
external verification separately. Elliptic additions and Jacobian additions
are different native units; do not divide their counts to claim a speedup.
Common priced work and a cross-method cost ratio stay null until an audited
cost model exists. Report peak/table memory and all failures/censored runs.

The existing optimized batched strong-rho implementation is the elliptic
reference. A resumable matched walk that changes batching or scheduling is a
separately named implementation; do not relabel it as the existing ecbench
method. Check the existing native ecbench integration and document any width,
subgroup-selection or Jacobian-adapter blocker with acceptance criteria.
Do not manufacture an ecbench audit certificate for external records.

## Correctness, scheduling, measurement and stop conditions

Before full jobs: test arithmetic against the existing independent fixture
implementation, verify pullback-addition compatibility, reject malformed
inputs, and compare resumed versus uninterrupted state and solutions. Small
controls only establish correctness; they are never full-size timings.

Build and test before timing. Use native ecbench isolation primitives and
the exclusive benchmark lock; pin the worker, record preflight, eviction,
actual affinity, NUMA placement, CPU/cgroup conditions and available hardware
counters. Record unsupported observations as missing. The current virtual
worker starts at L0; no stronger level is assumed. No builds or unrelated
CPU-heavy work during timed sections.

Measure one warmup, A/A controls, then at least five interleaved A/B rounds
for initial throughput calibration. Do not call a checkpoint slice or a rate
estimate a completed solve. Use raw per-round values and report spread.
Only completed, independently verified full solves have solve durations.
General wall-time comparisons require eight targets per curve, paired
confidence intervals excluding one, admissible isolation and the A/A control.
Until then report descriptive rates and completion status, no speedup claim.

Schedule current-worker work serially with atomic checkpoints, favoring a=1
for obtaining the first complete full-subgroup result while preserving a=0
progress. End a target only on independently verified recovery, explicit user
stop, or recorded infrastructure/resource failure. Record process IDs and
resume commands. Host disappearance is a censored run, not a completed solve;
current-worker persistence is not guaranteed.

Results: preserve raw outputs and hashes, implementation revision, host
manifest, public input hashes and replay receipts. Generate an evidence-linked
Markdown report, quantitative graph (or execution diagram if data insufficient)
and inspected PDF; copy performance visuals to `benchmarks/`. Update existing
relevant PRs in both repositories. Frozen construction evidence is immutable.

This experiment compares two representations of one subgroup and generic rho;
it does not modify index calculus. The WDSat frozen IC regression protocol is
inapplicable. Independent-host replay and a common priced native-work model
remain mandatory before a performance/security promotion.

## Initial environment

Current worker: five exposed x86_64 virtual CPUs, Intel Xeon Platinum 8573C,
four-CPU cgroup quota, 16 GiB memory limit. No dedicated machine supplied.
`conductor check` was attempted before editing; executable unavailable (127).
The source construction starts at crypto cdf13a965874ea45720649388f30b8b5291a7176
and cryptanalysis 2f893facd3435562f84db231dda0d5a8fdd257ff.
