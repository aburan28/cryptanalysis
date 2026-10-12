# Full ordinary N83 search with one Gaussian XOR matrix

The Q63 ordinary attempt activated one CryptoMiniSat Gaussian matrix
on the exact same width-18 XCNF as Q54. It reached the five-million-
conflict cap with stage status `bounded_unknown` in 496.816 solver
seconds and a 497.087-second target-dependent PDP interval. The
earlier default setting reached that cap in 336.204 solver seconds;
the separate local-host runs have unverified isolation and drifted
substantially, so their wall-time ratio is exploratory. The bounded
ABBA pilot in Q62 gave a mixed shorter-range timing signal.

| Same base, public point, formula and cap | Default Q54 | One matrix Q63 |
| --- | ---: | ---: |
| Usable base points before folding | 21,714,958 | 21,714,958 |
| Signed-Frobenius columns | 130,813 | 130,813 |
| XCNF raw SHA-256 | `fdefef5ea0f6...fa91ed` | `fdefef5ea0f6...fa91ed` |
| Active Gaussian matrices in solver log | 0 | 1 |
| Reported conflicts | 5,000,001 | 5,000,001 |
| Solver seconds | 336.204 | 496.816 |
| Target-dependent PDP seconds | 336.470 | 497.087 |
| Sampled peak solver RSS | 219,742,208 B | 120,406,016 B |

The [protocol](protocol.json) fixes public workload `df4396f4d8fc`,
raw target choice zero, one CryptoMiniSat thread, the unchanged
factor-base and formula hashes, five-million-conflict cap, 600-second
wall cap and 4 GiB sampled RSS stop. The target-generation scalar
appears only as a SHA-256 commitment. The [stage receipt](width18_ordinary.json)
retains raw solver output, compressed formula, memory samples and
exclusive phase costs. The full pair-root index is not allocated.

The Q62 [locked control](../n83-geometric-m5-gauss18-20261012/karatsuba_control.json)
returns SAT and passes group replay. [Independent Sage replay](sage_relation_replay.json)
checks that relation in a separate field representation and records
the bounded ordinary run. The checked Sage launcher saved [runtime
identity](sage_runtime_info.json) before the run. Run the read-only
audit from the repository root:

```sh
python3 experiments/n83-geometric-m5-gauss-ordinary18-20261012/verify.py
```
