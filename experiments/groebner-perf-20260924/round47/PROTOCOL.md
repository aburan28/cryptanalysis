# Exact tiled specialization and independent accounting

The proof protocol, fresh support-only original-equation symmetry guard, proof-pair eligibility, bounded fallbacks, complete roots and reduced-basis checks are those in [round45/PROTOCOL.md](../round45/PROTOCOL.md). No producer table, claimed rank, transform output or cached target establishes symmetry.

For an even fixed split x=2k, each coefficient slice is an N by N matrix A with N=2^k. A successful independent guard proves A=A^T. Boolean subset specialization is C=Z A Z^T, where Z is the subset-zeta matrix over GF(2). Split the original matrix into E,D,D^T,F. Recursively specialize E and F and fully specialize D, obtaining e,d,f. The four resulting blocks are e, e+d, (e+d)^T, and f+e+d+d^T. The last block is symmetric. Its diagonal receives only e, since d+d cancels in characteristic two.

The implementation finishes f before overwriting d, visits the lower triangle in blocks and mirrors complete values, then forms e+d in blocks and writes its transpose. A fixed leaf size of 16 uses the general axis-separated transform. Tile sizes 8,16,32 and the unblocked n control differ only in access order. No extra coefficient array is needed; recursion depth is logarithmic. The full output and supported problem size are still exponential. This remains O(N^2 log N), without an asymptotic solver or novelty claim.

For one slice, the full transform costs k*4^k XORs. Let T(k), M(k) count tiled XORs and mirror stores. For k<=4, T(k)=k*4^k and M(k)=0. With h=2^(k-1), the recurrence is:

```
T(k) = 2*T(k-1) + (k-1)*h*h + 3*h*(h-1)/2 + h + h*h
M(k) = 2*M(k-1) + h*(h-1)/2 + h*h
```

Counts are multiplied by (1+y+y*(y-1)/2)*ceil(equations/64), the number of feature/limb slices. For x=18,y=9,equations=31 there are 46 slices, each 512 by 512 with 32-bit words. `full_xors` describes the retained full-transform comparator; `actual_xors` is the executed count and equals the ordinary checker's `transform_xors`. `mirror_words` counts additional stores. These abstract counts are distinct and cannot be added into a wall-time speedup.

`requested_mode` and `selected_mode` distinguish explicit selection from fallback. General `axes` needs no symmetry, but this implementation requires an even fixed split. The tiled modes require the entire existing symmetry preparation to finish, including proof-pair matching and all soft budgets. If that preparation fails, the full loop runs even if coefficient symmetry was established before the failure. Fresh scatter and full certification remain mandatory. The accepted table cap (64 MiB), x<=20, y<=10, x+y<=30, equation count<=128, proof/assignment/root/basis caps and auxiliary symmetry limits remain unchanged.

`seconds` measures the transform section and is nested inside `stats.specialization`; do not add it again to specialization or query time. Symmetry guard time is also nested in specialization. Test-only `CHECKER_TRANSFORM_AUDIT` copies the freshly scattered original table, runs the selected mode, then independently executes the accepted full flat loop on the copy and compares every word. `audit_words`, `audit_bytes` and `audit_xors` report that additional work. Ordinary builds leave those fields zero. The audit build can allocate one extra table up to 64 MiB and is excluded from performance measurements.

The ABI metadata is reset at each native certification call and copied under the context lock. Configuration is explicit and serialized. The query adapter loads its checker under a unique module name so importing a comparator first cannot silently select another checker.
