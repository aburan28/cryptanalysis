# Mixed-rotation pair-output join matches the six-pair geometry

An exact **shared-seed, mixed-Frobenius-rotation four-atom inverse** now
applies to the two constrained blocks of the frozen six-pair ECC2K-130
candidate. It recovered the constructed product witness `(1112,1376)`
when the first pair was at rotation 26 and the second at rotation 39;
the frozen trace-zero control produced zero algebraic hits. Checked Sage
independently replayed all four curve points, both rotated pair sums, the
four-atom group sum, and its cofactor-four subgroup projection. The N41
control at rotations 10 and 15 likewise recovered `(24,72)` and rejected
its control. This connects the fast pair-output join to the candidate's
actual geometry rather than requiring a change in its factor-base policy.

## Exact join

Both source pairs have the same mask XOR seed `s`, but Frobenius rotations
`r1` and `r2` give field seeds `s1=s^(2^r1)` and `s2=s^(2^r2)`.
For each source pair product `p`, the setup solves

`(1+p^(2^(r1+1)))C²+p^(2^r1)C+s1²=0`

and the analogous equation at `r2`, retaining `C -> p` and `D -> p` in
two tables. Given a proposed four-atom reciprocal output `z`, the query
solves `(1+z²C²)D²+zCD+(z²+C²)=0` for each left-table coordinate and
looks up its roots in the right table. The product key is stored in the
unrotated source encoding, so the recovered pair products can be lifted
against the audited source masks. The [native implementation](native.cpp)
uses the retained field arithmetic and odd-degree half-trace quadratic
solver. On N131, the archived W14 rational-mask and folded-column map
filters each seed-one pair domain to **2,062 usable source pairs**;
each rotated output table has **4,124 distinct coordinates**. N41 retains
all 32 algebraic product states as a positive-control superset.

The [fixture generator](prepare.py) derives both mixed-rotation outputs
from archived raw source points. The [frozen protocol](protocol.json)
binds its [inputs](inputs.json), binary and source hashes, W14 support,
the accepted [Sage runtime](sage_runtime_info.json), one worker, 30-second
per-run cap, 4-GiB RSS limit, and run order. The [native results](result.json)
preserve setup and target-dependent proposed-output query clocks
separately. The [independent Sage audit](sage_audit.json) confirms the
positive group witnesses and every terminal status. The
[terminal audit](terminal_audit.json) binds source/input hashes, four raw
native results, resource caps, and that Sage replay.

| Field and pair rotations | Case | Pair outputs per table | Algebraic hits | Reusable setup | Proposed-output query | Peak RSS |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| N41, 10 and 15 | constructed | 33 | 1 | 0.000434 s | 0.000219 s | 1,622,016 B |
| N41, 10 and 15 | trace-zero control | 33 | 0 | 0.000445 s | 0.000219 s | 1,638,400 B |
| N131, 26 and 39 | constructed | 4,124 | 1 | 0.215051 s | 0.357543 s | 3,637,248 B |
| N131, 26 and 39 | trace-zero control | 4,124 | 0 | 0.208624 s | 0.341649 s | 3,719,168 B |

These are one-host stage diagnostics without CPU isolation. The exact
observations are the recovered product keys, group replay, complete
algebraic scans, and 4-GiB headroom. `candidate_id` remains `null` for
this partial-sum component.

## Next target-conditioned gate

The current kernel checks one proposed `z` for one seed. Multiplying the
observed N131 control query interval by all 16,383 nonzero W14 seeds gives
about **5,597 seconds per proposed output** for a literal seed sweep;
this is a simple source-bound extrapolation, not a measured complete
sweep. The public point must eliminate seed families or constrain several
partial sums before this oracle runs. The next experiment should derive
candidate `z` values and seed restrictions jointly from the published Q
and the two other still-free blocks. First measure whole-family rejection
and independently replay one ordinary relation on the unpinned N41
public point. Only a source-bound one-worker/600-second/4-GiB projection
should trigger the frozen N131 public-point query.
