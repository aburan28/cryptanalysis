# Radix-929 bounded top-state scalar multiplication format

Twelve radix-929 unit-orbit windows and one directly indexed bounded top
state reconstruct every integer scalar modulo the secp256k1 subgroup order.
Lean 4.34.1 proves the twelve-step top bound `3Q≤679762`, exact
reconstruction and scalar congruence, a unique unit-orbit sector for each
nonzero top state, and the finite row bound. The exhaustive table audit checks
all 821,953 admissible top states and their 136,993 orbit ranks.

| Exact format count | Radix 929, 12 windows + top | Radix 943, 13 windows | Difference |
| --- | ---: | ---: | ---: |
| Ordinary orbit entries per window | 143,841 | 148,209 | Format-specific |
| Total affine point entries | 1,863,085 | 1,926,717 | -63,632 (-3.30%) |
| Affine point bytes at 64 per point | 119,237,440 | 123,309,888 | -4,072,448 |

The radix-929 ordinary residue map has 863,041 four-byte entries
(3,452,164 bytes); its canonical digit list has 143,841 four-byte pairs
(575,364 bytes). The top rank uses 953 four-byte prefixes (3,812 bytes) and
integer row bounds. These auxiliary counts are separate from point bytes.
The rank is `1 + prefix[u-1] + b - b_low(u)` for canonical top pair
`(-u,b)`, with rank zero reserved for the origin.

| Frozen panel | Cases | Reconstructed group points | Radix 929 modeled products | Radix 943 modeled products | Radix 929 modeled rotations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Design panel | 4,096 | Scalar congruence checked | 484,152 | 484,163 | 9,016 |
| Fresh holdout | 512 | 512/512 matched | 60,521 | 60,548 | 1,129 |

The paired count uses the same nearest scalar representative, input panel,
and frozen Pareto accumulation plan. Both formats use 13 point terms for
every case in these panels. Products are source-model counts; the radix-929
top lookup and table construction have not been timed in native code.
Design source and receipt were committed at
`9a103281a` before the holdout with seed `20261012929` was generated.

Run the reproducible checks from the repository root:

```sh
python3 experiments/prime-j0-radix929-topball-20261012/check.py --check
python3 experiments/prime-j0-radix929-topball-20261012/topball.py --check
python3 experiments/prime-j0-radix929-topball-20261012/screen.py --check
python3 experiments/prime-j0-radix929-topball-20261012/holdout.py --check
python3 experiments/prime-j0-radix929-topball-20261012/holdout_replay.py --check
```

The next implementation step is an opt-in native top lookup and point table,
followed by matched full-operation benchmarks on a host that satisfies
`docs/ISOLATED_BENCHMARKS.md`. The Runpod container currently available
does not provide auditable host-level CPU isolation; no CPU speed ratio is
reported from it.
