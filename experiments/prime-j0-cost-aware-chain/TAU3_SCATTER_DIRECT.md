# Direct residual-pair τ multiplication

The [scattered pair table](TAU3_SCATTER_MATCHING.md) uses exact maximum
matching to minimize group additions for a fixed width-three τ expansion and
prepared action set. This follow-up keeps the same point table and uses a
deterministic online selector. It first takes every available pair within a
six-step block. It then scans the unmatched three-step blocks from low to
high position and takes the first later unmatched block with a prepared
cross-pair action. It stops there, without building the remaining pair graph
or searching alternating paths.

Every action represents the same group element as the blocks it covers, so
pairing disjoint blocks preserves the scalar result. Since the selector begins
with all complete-table pairs and only adds cross-pairs, its addition count
cannot exceed the complete-table count. It can exceed exact matching's count;
the difference is measured below. The method is variable-time and intended
for public scalars.

## Frozen policy and prospective operation panel

[`tau3-scatter-direct-design.json`](tau3-scatter-direct-design.json) froze this
policy after the earlier scattered-pair panel was inspected. Only then did
[`make_tau3_scatter_direct_inputs.py`](make_tau3_scatter_direct_inputs.py)
produce a 32,768-scalar fixture disjoint from all five prior scalar fixtures.
Both selectors use the same already-frozen extra-point table. The existing
exact checker independently replayed the new fixture, followed by the
[`direct checker`](check_tau3_scatter_direct_panel.py). Each checked all 32,768
Eisenstein scalar identities and 184 elliptic-curve point outputs.

| Curve | Complete-table additions | Exact matching | Direct selector | Direct saving | Exact saving retained |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 47,682 | 44,231 | 44,261 | 3,421 (7.18%) | 99.13% |
| `j0-56` | 97,704 | 93,205 | 93,593 | 4,111 (4.21%) | 91.38% |

The direct selector gives up 30 and 388 additions relative to exact matching
over 16,384 scalars per curve. Its point storage and preparation are identical
to exact matching: 2,494 or 4,802 point slots, with 2,418 or 4,669
preparation additions. The complete-table control uses 1,372 or 2,401 point
slots, with 1,296 or 2,268 preparation additions.

The native mode `tau3-scatter-direct-pos` reuses the scattered point table
and skips the augmentation phase. Its fresh 24-arm panel includes the
complete-table, exact-matching, and direct modes in rotating order. Every arm
independently verified all 4,096 output points in its case. The three output
digests matched for each case, and all addition and pair counts matched the
two frozen Python models. There were no fallbacks. The release `test_curve`
suite passed 2,311,742 checks, including scalar edges, identity, and forced
fallback controls for the direct mode. A warnings-as-errors
UndefinedBehaviorSanitizer build passed the same 2,311,742 checks and the
24-arm native panel.

The native receipt retains local timings as exploratory diagnostics only.
There is no host-isolation receipt or CPU speedup claim. The table's extra
preparation, point bytes, and static maps remain part of the resource tradeoff.

## Isolated replay

[`make_tau3_scatter_direct_isolated_manifest.py`](make_tau3_scatter_direct_isolated_manifest.py)
binds the new frozen inputs, one native binary, independently replayed output
digests, and three alternating-order repetitions to the serial isolated
benchmark service. Generate two manifests on a qualifying Linux host: one
pairing direct against exact matching and one pairing direct against the
complete-table control. Set `--reference-mode tau3-fused-pos` for the latter;
the default is `tau3-scatter-pos`.

```sh
python3 experiments/prime-j0-cost-aware-chain/make_tau3_scatter_direct_isolated_manifest.py \
  --binary /workspace/build/scatter/ca_tau_chain_bench \
  --workdir /workspace/cryptanalysis \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --reference-mode tau3-fused-pos \
  --output /workspace/isolated-bench/tau3-scatter-direct-vs-full.json
python3 scripts/isolated_bench.py probe \
  /workspace/isolated-bench/tau3-scatter-direct-vs-full.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/tau3-scatter-direct-vs-full.json
```

The paths and CPU IDs are examples. The timer covers a 4,096-scalar batch
after point preparation and before independent output replay. This is a
scalar-multiplication throughput study, not a one-target DLP comparison.
The service must reject any host that fails its CPU and NUMA isolation
preflight; no ratio from that host is a controlled speedup result.
