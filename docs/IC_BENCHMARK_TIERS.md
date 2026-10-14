# CPU benchmark tiers for index calculus

The primary result is a verified single-target online interval for an exact
IC candidate and a strong rho solve on the **same public point**. Each
candidate retains its canonical `IC1` manifest, workload and run IDs, five
exclusive online phases, setup and resource receipts, and independent scalar
replay as required by [AGENTS.md](../AGENTS.md). Host tier is a separate
measurement property, never part of the candidate identity.

## Tier 0: physical-host isolation

Tier 0 uses the [isolated benchmark service](ISOLATED_BENCHMARKS.md) or an
equivalent host-level record. The physical CPU model, complete core and SMT
topology, exclusive partition, NUMA memory policy, fixed frequency, IRQ
routing, absence of quotas, affinity and noise counters must pass the strict
preflight. The service's existing strict mode remains the Tier 0 runner.
Its host-preflight rejection is a Tier 0 result; a separately executed panel
may still qualify for Tier 1 under the rules below.

## Tier 1: dedicated cloud allocation

Tier 1 accepts a dedicated cloud VM or Pod allocation, including a RunPod
instance, without requiring evidence that the **physical** host is exclusive.
The allocation must be reserved for the benchmark panel for its full
duration. Record provider, allocation and instance type, region or zone,
instance start/end receipts, CPU model, visible core/SMT/NUMA topology,
visible affinity, cgroup CPU and memory limits, kernel, OS, compiler,
binary/source hashes, and the exact target and factor-base manifests.
Record the resource request and actual limit, including worker count, memory
guard and time cap. An ephemeral GitHub Actions runner may be used at this
tier if the same allocation and panel receipts are available. Record its
exposed runner class and mark a provider-hidden physical instance type
unknown. A workflow name or visible affinity mask alone is insufficient
evidence.

After selecting the factor base on a separate panel, pre-register at least
five fresh, distinct public target points before the Tier 1 timing panel.
Run the timing panel on one allocation. Declare one exposed logical CPU set,
pin the parent before launching children, record its effective mask and each
arm's worker count, and confirm from the frozen launch code or a child
readback that both arms inherit that same set. A one-CPU set is permitted;
multiple exposed CPUs are permitted when every worker stays in the declared
set. Each point is a primary one-target workload:
finish and independently replay the IC answer and a strong-rho answer on
that **same point** with the same declared CPU and memory envelope. Run five
paired comparisons in alternating order, for example `IC,rho` then
`rho,IC`, without warming a cross-target distinguished-point table or
charging setup to only one arm. Target-independent IC setup remains a
separate receipt; each online clock starts at the first target-dependent
operation and ends after the recovered scalar is independently verified.
If scalar replay is outside the producer interval, record its duration
separately and use the same timing boundary for both arms.

Record raw start/stop timestamps and monotonic elapsed time for every arm,
including timeout, OOM, incorrect result, or cancellation. Sample cgroup
throttling and memory events, CPU steal time, involuntary context switches,
interrupt counters, frequency where exposed, and an A/A calibration workload
before and after each pair. Declare calibration limits and acceptance rule
before seeing results. Reject a pair when correctness fails, its resource
cap is crossed, throttling or OOM occurs, or calibration exceeds its frozen
noise bound; retain its receipt. Do not replace an excluded pair after
looking at its timing. A whole-panel retry uses a fresh recorded allocation
and keeps the first panel.

For a Tier 1 speedup report, require all five preregistered pairs to pass,
the IC interval to be shorter on all five points, and the preregistered 95%
paired ratio interval to have a lower bound above one. Report every paired
ratio, the median ratio, arithmetic mean online times, resource peaks,
calibration results, and that interval. State the provider,
instance and tier next to the result. These observations support a speedup
for the frozen target law and instance class; additional hosts strengthen
portability. A panel with fewer than five valid pairs remains a stage result.

## Exploratory measurements

Single cloud runs, unmatched hosts, reused public points chosen during
tuning, missing noise receipts, and incomplete pairs remain exploratory.
They can establish correctness, capacity and phase costs. Preserve their
raw rows, status and caps. Never infer a missing phase cost or a failed
speedup as zero.
