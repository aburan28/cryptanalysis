# Exact independent multiplier identities

Work in the Boolean quotient over GF(2), where each variable satisfies z_i^2=z_i. The validated specialized equations have degree at most two in y residual variables, and each supplied multiplier has degree at most one. Pack each original-equation coefficient F_M and each multiplier coefficient u_i by equation index. M is a numeric squarefree monomial mask; F_M=0 when M has degree greater than two.

For an output monomial M, its coefficient in the sum of multiplier-times-equation products is the parity of

```
(u_0 & F_M) XOR XOR_{i in M} [u_i & (F_M XOR F_(M without i))].
```

The formula follows by enumerating all unions of a degree-zero/one multiplier mask with a degree-at-most-two equation mask. Every output has degree at most three, so checking those masks covers the complete polynomial. In grouped mode, accumulate the individual AND terms before one parity. In factored mode, use

```
[(u_0 XOR XOR_{i in M} u_i) & F_M]
    XOR XOR_{i in M} [u_i & F_(M without i)].
```

Omit terms with nonexistent F_M. Across two equation limbs, XOR the limb contributions before the final parity; linearity of parity makes cancellation across limbs exact. The checked identity must equal constant one. These elementary Boolean identities do not change the exponential branch count or establish a new Gröbner algorithm.

The checker constructs its layout from numeric masks, independently of the producer. The degree bound is checked on the current input before specialization. The layout occupies at most 16 KiB per context. Local modes use a fixed 112-word (896-byte) scratch array and overwrite every used word on each record. Dense modes use 1,024 identity bytes; packed mode uses 128 identity bytes; grouped modes use scalar accumulators. These reported sizes describe logical live payloads, not compiler stack frames or measured process peaks. No second coefficient table is allocated by ordinary identity modes. The accepted coefficient table cap is 64 MiB; x<=20, y<=10, x+y<=30, equations<=128 and all inherited proof, root, assignment, basis, partial and symmetry budgets are unchanged.

Let L=ceil(equations/64), F=1+y+choose(y,2), G=F+choose(y,3). Dense parity calls are (y+1)FL. Grouped/factored parity calls are G, with limbs folded first. Grouped ANDs remain (y+1)FL; factored ANDs are [1+2y+3 choose(y,2)+3 choose(y,3)]L, plus [y+2 choose(y,2)]L witness XORs. Local modes copy FL words and report later cached reads separately. Counts include accumulator updates from zero and describe source operations. Compiler elimination, vectorization and physical memory traffic are not inferred from them.

`identity_check_stats` reports the selected mode, attempted and reused records, actual parity calls, dense-equivalent parity work, ANDs, accumulator/witness/identity XORs, original-table reads, local reads/copies, and storage payloads. `stats.multiplier_parities` and `symmetry_check_stats.avoided_multiplier_parities` count the selected mode's actual and avoided parity calls. `dense_equivalent_parities` is a separate diagnostic for reconciliation with the old checker, never actual executed work. Malformed or invalid records retain attempted work; successful record counts are reconciled independently against the proof.

`identity_audit_test=True` selects an explicit test-only build. It executes the candidate check, materializes the candidate polynomial a second time, independently repeats the old dense multiplication, and compares all 2^y output coefficients. It uses two extra fixed 1,024-byte arrays and reports extra records, coefficient comparisons and parity calls. It is excluded from performance measurements and cannot be combined with another test-build selector. Native coefficient replay separately instruments table reads and compares every coefficient against an equation-by-equation Python oracle.

Configuration is explicit and mutex-protected. Per-call metadata is reset and copied under the Python context lock. The adapter pins its producer and setup checker factories and loads the new checker under a unique module name. Current equations, proof metadata, symmetry admissibility and all fallback decisions are recomputed per query.
