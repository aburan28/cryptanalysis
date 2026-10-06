# Recursive symmetric Boolean transform experiment

This is a standalone coefficient-kernel experiment. It neither produces nor accepts a Gröbner basis. The accepted round45 implementation and its benchmark are frozen. No implementation in this directory is connected to production or automatic dispatch.

For a symmetric coefficient matrix A of order N=2^k, the complete specialization is C=Z A Z^T, where Z is Boolean subset incidence over characteristic two. Partition A into equal blocks E,D,D^T,F. The corresponding subset matrix is [[Z,0],[Z,Z]]. Recursively specialize the two symmetric diagonal blocks E,F, and fully specialize the general off-diagonal block D. The final blocks are E, E+D, (E+D)^T, and F+E+D+D^T. Compute the last block before changing D. Its diagonal needs only F_ii XOR E_ii, since the two D_ii terms cancel.

The native candidate operates in place with a stride for each recursive submatrix. It uses logarithmic call depth and no additional coefficient table. The test wrapper independently scans the input matrix for exact symmetry before selecting a symmetric kernel; asymmetric inputs execute the accepted complete transform. Future checker integration must use the checker's fresh original-ANF guard, never the producer's symmetry assertion. Odd fixed-variable splits, disabled symmetry, insufficient workspace, or an incomplete/budget-exhausted guard retain the full transform.

The derived recurrence counts word XORs and mirror stores separately:

- T(0)=0; T(k)=2T(k-1)+(k-1)(N/2)^2+3h(h-1)/2+h+h^2, h=N/2.
- T(k)=[N^2(2k+1)-N(k+1)]/4, versus kN^2 for the accepted complete transform.
- Mirror stores M(k)=[3N^2-N(k+3)]/4.

At k=9 this predicts 1,243,904 XORs and 195,072 mirror stores per coefficient slice. The prior triangular proposal predicts 1,705,216 XORs and 130,816 mirror stores; the full transform uses 2,359,296 XORs. These counts exclude index arithmetic, branches, function calls, guard work and cache effects. They do not establish elapsed-time improvement. All three algorithms remain O(N^2 log N); this is a conditional constant-factor experiment, with no algorithmic novelty or asymptotic claim.

The native screen also includes full-transform leaves of order8,16,32 to preserve contiguous vector loops and reduce recursion overhead. Before any native execution, leaf16 is the declared timing primary; pure recursion and the other leaf sizes remain named alternatives. For a leaf order2^t, replace 2^(k-t) instances of T(t) by t*4^t and omit those leaves' mirror stores. Count these extra XORs explicitly. No result-dependent leaf selection is enabled.

Before timing, validate every output coefficient against the unchanged full transform, and small cases against direct subset incidence. Cover all 1,032 symmetric binary matrices of orders two and four, seeded 32/64-bit matrices through N=1024, dense/sparse/diagonal/zero inputs, deliberately asymmetric controls, ABI bounds, optimized and undefined-behavior-sanitized binaries. The separate Python reference additionally covers up to128-bit coefficients. Preserve source/binary hashes and every failure. No build, validation or kernel timing may overlap the currently running round45 complete-query benchmark.

Only a passing kernel can advance to full independent-checker integration. That step must retain all malformed-proof, incomplete-root, canceled-input, wide-equation and soft-fallback controls, and compare complete query time on the same frozen inputs. A kernel-only timing result cannot be presented as a verified-query, F4/F5, GPU, or IC speedup.
