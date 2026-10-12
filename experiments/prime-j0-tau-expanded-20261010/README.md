# Tau-preexpanded nineteen-window scalar format

The 19-window table stores both `P` and `tau(P)` as affine points for each seed. Each digit selects its precomputed tau exponent; all selected points accumulate in one Jacobian bucket. This removes the online degree-three tau map and final projective addition. Grouped unit powers need at most two bucket rotations.

The format retains 2,916,756 bytes across 21,949 table slots, the same byte count as the orbit-X format. Compared with the original 19-window format, this buys a different operation path for 1,404,736 additional retained bytes. The evaluator is a public-scalar research path with scalar-dependent table indices.

`native-tau-expanded-delta.patch` applies after the 17-window, 19-window, and orbit-X patches in the scalar PR. The source receipt binds the scratch implementation before the fresh panel draw. The native tests check all 21,930 nonidentity `tau(P)` table points against the separate native tau map, 4,096 prior scalar outputs with 128 independent binary point checks, and the complete 106-test release suite. CPU timing requires the isolated benchmark preflight.

The [fresh replay](FRESH_RESULTS.md) records 4,096 disjoint post-freeze scalars, independent point expectations, three native output streams, and source and result verifiers.

The [point-kernel operation diagnostic](OPS_DIAGNOSTIC.md) counts native field wrapper calls for those same scalars in all three formats, with its counter patch and log bound to the frozen source. It records a 40,697-multiplication and 12,288-squaring reduction relative to the original nineteen-window point kernel.

## Exact one-bucket identity

Write the chosen scalar representative as `a + b*tau` modulo the group order. The exact radix recoder gives a finite sum of window digits

`a + b*tau = sum_j 2^h_j * u_j * tau^e_j * (a_j + b_j*tau)`,

where `h_j` is the preceding width sum, `u_j` is one of the six units, `e_j` is zero or one, and `(a_j,b_j)` is a stored seed. For each window and seed the paired table holds

`T[j,seed,0] = [2^h_j](a_j + b_j*tau)G` and `T[j,seed,1] = tau(T[j,seed,0])`.

The endomorphisms commute with doubling and with each other, so summing `u_j*T[j,seed,e_j]` produces `[a+b*lambda_tau]G = [k]G`. The unit power groups use a single accumulator in a local gauge: while processing power `p`, it holds `omega^(-p)` times the accumulated true point. Moving from power `p` to `q` rotates the accumulator by `omega^(p-q)`; the final rotation restores the true point. The native code checks exact recoder termination and checks every stored nonidentity tau image against the separate native tau map.

The general use of endomorphisms for scalar decomposition and of precomputed endomorphism images is established in [Smith's GLV/GLS lattice treatment](https://eprint.iacr.org/2013/672) and the [FourQNEON precomputation algorithm](https://eprint.iacr.org/2016/645.pdf). This construction combines the exact nineteen-window six-unit residue cover with paired degree-three images and a one-bucket gauge schedule under a measured retained-byte budget.
