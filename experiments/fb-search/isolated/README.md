# One-target IC-versus-rho panel for the isolated benchmark service

AGENTS.md allows a CPU wall-time speedup claim only with a receipt from the
[isolated benchmark service](../../../docs/ISOLATED_BENCHMARKS.md). Every IC-versus-rho wall time
in `fb-search` so far is exploratory. This directory holds what that service needs to turn the
one-target comparison into a controlled result. **The controlled run itself has not been done.** It
needs a qualifying host, and this one is not.

## Files

- `one_target.py`: the benchmark executable. One process solves one frozen public target and prints
  the runner's `key=value` fields (`online_ms`, `verified`, the pairing fields, `candidate_id`,
  `workload_id`).
  - **`--variant ic`** runs the ic-bench m = 2 pipeline (`PDP2ht`, walk rerandomization). Setup runs
    first, untimed: the factor base, relation collection to the achievable rank, relation LA and log
    checks. `online_ms` is the target's own interval: from the first rerandomization to the independent
    scalar replay `[log Q]G == Q`, with every failed attempt inside.
  - **`--variant rho`** runs ic-bench's one-target Pollard rho on the same point, timed from the first
    walk computation to `[s]G == Q`.
  - **Verification.** `verified=1` requires scalar replay and equality with the fixture scalar.
- `make_ic_isolated_manifest.py`: writes the frozen panel in the runner's schema. It uses 64 n = 19
  and 32 n = 23 targets, on the best `online-ht` bases:
  - `IC1N19Ckb1fb78PDP2htRCsampleLAgaussTDpdpISO0h286621b6083e` (geomtraceu, l = 6, seed 4);
  - `IC1N23Ckb1fb266PDP2htRCsampleLAgaussTDpdpISO0h33de8ed9a126` (geomtraceu, l = 8, seed 2).

  Targets follow `s = 1 + SHA-256("fb06-ic-rho-v1:<curve_id>:<index>") mod (r - 1)`.
- `exploratory_panel.py`: runs a manifest directly, with the runner's pairing rules (alternating
  order, `verified=1`, matching pair fields) but **no** preflight, pinning or noise gate. Its rows
  carry `"controlled": false`.
- `../test_isolated.py`: covers three things.
  - The fixture law is frozen.
  - A generated manifest passes `isolated_bench.py`'s own `require_manifest`.
  - Both variants verify the same target, with equal pair fields.

## Running it as a controlled result

On a host prepared as `docs/ISOLATED_BENCHMARKS.md` describes: a physical Linux host under
administrative control, with an empty cgroup v2 isolated partition, `nohz_full`, a fixed performance
frequency, IRQs moved off the partition, and `numactl`.

```sh
python3 experiments/fb-search/isolated/make_ic_isolated_manifest.py \
  --python /usr/bin/python3 --workdir /workspace/cryptanalysis \
  --cgroup /sys/fs/cgroup/benchmark-isolated --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --output /workspace/isolated-bench/ic-rho-panel.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/ic-rho-panel.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit /workspace/isolated-bench/ic-rho-panel.json
```

The CPU IDs and NUMA node are examples; use the host's verified topology. The service publishes a
paired speedup only if every pair verifies and every isolation and noise gate passes.

## This host does not qualify

`results/isolated-probe-cursor-vm.json` is `isolated_bench.py probe` on the cloud-agent VM: `ok: false`,
with 18 problems. The main ones:

- no root;
- a KVM guest (`clocksource=kvm-clock tsc=unstable`), not bare metal;
- no isolated cgroup partition;
- no `nohz_full`;
- no fixed-frequency governor;
- no `numactl`;
- IRQ affinity overlapping the benchmark CPUs.

A RunPod Pod is a container and, by the service documentation, will usually fail the same gate. A
controlled receipt needs a physical host whose administrator can apply the kernel and cgroup
settings.

## Exploratory panel on this host (not a controlled result)

Data: `results/ic-rho-exploratory.jsonl`; summary: `results/ic-rho-exploratory-summary.json`, from
`exploratory_panel.py --summarize`. The panel ran 44 cases (n = 19 targets 0-31 and n = 23 targets
0-11), and every IC and rho answer verified. The geometric-mean rho/IC ratio is:

- n = 19: 0.97, bootstrap 95% interval [0.62, 1.46];
- n = 23: 2.69 [1.45, 5.31].

The table is in `../README.md` ("One-target IC versus rho, exploratory panel").

**Fairness caveat.** Both variants use the same Python and ctypes field arithmetic. Rho's single walk
pays one ctypes call per group operation, while IC's attempts are batched. An all-C pair would change
the ratio: in `../ABOVE_LIMIT.md` Sec. 4e, a C rho step is 58 ns. So this panel measures these two
implementations, not the algorithms.
