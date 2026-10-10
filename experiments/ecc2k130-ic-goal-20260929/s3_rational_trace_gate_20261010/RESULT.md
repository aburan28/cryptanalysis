# Rational pair outputs make local S3 links automatically solvable

On the binary Koblitz curve `y²+xy=x³+1`, a nonzero reciprocal
x coordinate `c` belongs to a rational point exactly when
`Tr(c+1/c)=0`. This makes the trace condition in the target-split
half-trace solver an exact **rationality test**. For any two rational
reciprocal coordinates `c,z`, the third summation equation has two
field roots when `cz≠1` and one linear root when `cz=1`. Thus a local
S3 link between already valid pair outputs does not reject a candidate
on its own; useful early rejection must come from the sparse source
domains and their joint target constraint.

## Derivation

For `x≠0`, dividing the curve equation by `x²` and writing `u=y/x`
gives `u²+u=x+1/x²`. The Artin–Schreier equation is solvable over
`GF(2^n)` exactly when its right-hand side has absolute trace zero.
Because `Tr(1/x²)=Tr(1/x)`, setting `c=1/x` yields
`Tr(c+1/c)=0`.

For rational `c,z`, normalize reciprocal S3 as in the
[split half-trace implementation](../n131_mixed_s3_halftrace_split_20261010/RESULT.md):

`v²+v=(c+1/c+z+1/z)²`.

Its right-hand trace is the XOR of the two rationality trace bits, hence
zero. When `cz≠1`, the associated quadratic has two distinct roots;
the `cz=1` branch is linear. The result is independent of the source
mask seed, sign, or target point. Source membership and column
distinctness remain separate conditions.

## Frozen support checks

The [protocol](protocol.json) binds independent bit-field arithmetic,
the archived N41 raw diagonal atoms, the frozen mixed-rotation output
controls, and the packed N131 64-seed index before the
[run](audit.py). The run used one worker, a 120-second cap, and a
4-GiB RSS cap; its [receipt](result.json) retains wall and memory.
The [terminal audit](terminal_audit.json) checks all source hashes,
limits, and exact counts.

| Exact support | Rationality result | Local S3 result |
| --- | --- | --- |
| N41 raw source, rotations 10 and 15 | 1,956 signed pair states, 978 distinct coordinates per rotation; every coordinate has trace bit 0 | For each of the constructed and trace-zero proposed outputs, all 978 left coordinates yielded **two distinct** field roots |
| N131 packed W14 source, rotations 26 and 39, seeds 1–64 | All **264,202** left entries carry trace bit 0; 192 entries had that bit independently recomputed | Both frozen proposed outputs have rationality trace bit 0, so the theorem gives local S3 roots for every valid left entry |

The N41 run reconstructed raw points from the archived source, checked
curve membership, generated every usable signed pair, and checked both
roots through explicit group addition and the S3 polynomial. The N131
run parsed every packed trace flag and independently recomputed sampled
traces using a separately built field-trace mask. The two N131 proposed
outputs were checked through the same mask. The completed audit took
under two seconds on this host; its wall time is a correctness-stage
measurement, not a CPU speedup result.

## Consequence for the next target gate

The earlier fixed-seed N41 algebraic product superset contained some
non-rational pair-output coordinates, so its trace test rejected those
members. The usable N131 W14 source has already filtered to rational
points; all 264,202 tested entries share the passing trace bit. An
upper-chain solver should therefore propagate exact *pair-output
membership* and distinct-column constraints together with the public
point while several blocks remain free. A trace-only or S3-root-only
family filter cannot provide that pruning on this source. The next
N41 public-point experiment should measure how many joint output
families are removed before mask-pair expansion, then independently
replay an ordinary relation and bound the corresponding N131 work.

This is a structural stage result with `candidate_id: null` and no
complete-pipeline timing row.
