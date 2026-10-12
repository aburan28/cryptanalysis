# N83 geometric width and root-index capacity frontier

On `EC1N83Ckb1h876c2921cb64`, the shifted width-11 base has **1,096
signed-Frobenius columns and 181,936 usable subgroup points**. Its full
`83K²` packed root index needs 3,190,429,696 bytes of 16-byte root records;
adding the current polynomial x/y cache raises the deterministic payload to
**9,571,289,088 bytes**, beyond an 8 GiB process cap before allocator and
query overhead. Independent Sage replay verified all ten enumerated bases,
every seed projection, subgroup membership, and canonical key file.

## Frozen geometry and allocation model

For each width `d=9,...,13`, the [protocol](protocol.json) enumerates all
`2^d` x-coordinates in `W_d=span(gamma_1,...,gamma_d)` and in
`gamma_82+W_d`, where the `gamma` values are the frozen type-II normal basis
of `GF(2^83)`. Each lift on `y²+xy=x³+1` is multiplied by the cofactor four;
identity projections are discarded and the remaining points are folded by
sign and 83 Frobenius powers. Every retained column has 166 distinct subgroup
points. `K` counts columns and `B=166K` counts usable points before folding.

The full pair-root index has `83K²` states. Two 16-byte root records require
32 bytes per state. The current cached-coordinate layout adds two 16-byte x/y
pairs, 64 bytes per state. These are exact payload counts for that layout,
**lower bounds on process RSS**, rather than measured full-index memory.

| Width and base | `K` | Actual `B` | Root records, GiB | Root + x/y cache, GiB | 8 GiB cache payload |
| --- | ---: | ---: | ---: | ---: | --- |
| 9, linear | 240 | 39,840 | 0.142 | 0.427 | fits |
| 9, shifted | 276 | 45,816 | 0.188 | 0.565 | fits |
| 10, linear | 474 | 78,684 | 0.556 | 1.667 | fits |
| 10, shifted | 543 | 90,138 | 0.729 | 2.188 | fits |
| 11, linear | 1,016 | 168,656 | 2.553 | 7.660 | 365 MB headroom before overhead |
| 11, shifted | **1,096** | **181,936** | **2.971** | **8.914** | exceeds cap |
| 12, linear | 2,031 | 337,146 | 10.204 | 30.610 | exceeds cap |
| 12, shifted | 2,130 | 353,580 | 11.222 | 33.667 | exceeds cap |
| 13, linear | 4,079 | 677,114 | 41.165 | 123.467 | exceeds cap |
| 13, shifted | 4,125 | 684,750 | 42.089 | 126.269 | exceeds cap |

The table rounds GiB only for display; [frontier.json](frontier.json) contains
the exact byte counts, lift and duplicate counts, `C(B,4)/r` and `C(B,5)/r`
uniform-target subset first moments, source digests, and ten complete sorted
canonical key files. A first moment is a combinatorial expectation and does
not measure ordinary-query relation yield or novel matrix rank. The width-11
linear cache payload leaves 364,918,784 bytes below 8 GiB; actual fitting
depends on the full implementation's allocations.

## Reproduction and checks

The checked Sage launcher produced [runtime information](sage_runtime_info.json)
before enumeration. From the repository root in a fresh copy of this
directory, run:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/koblitz-n83-index-design-20260929/Q20261012_N83_WIDTH_FRONTIER/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-n83-index-design-20260929/Q20261012_N83_WIDTH_FRONTIER/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-n83-index-design-20260929/Q20261012_N83_WIDTH_FRONTIER/verify_sage.py
```

Both producers refuse to overwrite existing evidence. The independent
[Sage replay](independent_sage_replay.json) reports `PASS` and checks the
normal-basis bridge into an irreducible polynomial representation, every
projected point against the prime-order subgroup, complete key bytes and
hashes, and the state and payload arithmetic. The ten enumeration scan calls
summed to 8.335 s, and Sage replay took 20.4 s locally; these are exploratory
CPU costs. The exact
counts and allocation bounds are the result.

The next experiment should compare the **shifted width-11 root-only layout**
with the **shifted width-10 cached-coordinate layout** on frozen ordinary
queries. It must count exact hits, verified relations, novel rank, all failed
attempts, full target-dependent stages, and peak RSS under the same 8 GiB
cap. A candidate ID and one-target online speedup remain unset until the
complete method and same-point rho reference are measured.
