# Exact two-free-pair completion on the frozen N41 public target

This experiment tests a target-conditioned completion oracle for the
[ECC2K-130 pair-block goal](../NEXT_TARGET_COUPLED_BLOCK_GOAL.md). It uses the
frozen N41 W6 curve `EC1N41Ckb1h7d5e80d3c4d0`, eight slots, four same-rotation
pair domains, 256 usable base points, 26 folded columns, and public
`Q=(1458168294740,1672312028033)`. Its proposal label is
`Q20261008191400`. No complete IC candidate exists, so candidate and run IDs
remain null.

## Design

Let `U0,U1` be selected exact pair sums and `R=Q-U0-U1`. The last two pair
domains each have 1,956 signed point outputs and 978 distinct x coordinates.
The binary curve `y^2+xy=x^3+1` gives the exact Semaev condition

`S3(a,b,t)=(ab+at+bt)^2+abt+1=0`,

where `a=x(U2)`, `b=x(U3)`, and `t=x(R)`. Since each exact output domain is
closed under point negation, an x solution can be lifted to the required
group signs. The native method checks the actual group points and all eight
folded columns before accepting a row. Exceptional identity or equal-x
branches use the group law directly.

The first implementation constructs `F3(Z)=product_(b in X3)(Z-b)` once. For
each residual, it builds `N_R(Z)=product_(a in X2) S3(a,Z,x(R))` and tests
`gcd(F3,N_R)`. A nonconstant gcd is the exact x-coordinate membership test.
The [Sage protocol](protocol.json), [source](run_sage.py), and
[result](result.json) retain its inputs, clocks, controls, and hashes.

The second implementation scans `X3` and computes the two possible x
coordinates of `R+U3` and `R-U3` using one batched field inversion over all
978 denominators. It hashes the implied point in the exact `U2` domain.
This avoids the 978-by-978 pair-sum builder used by Q1448. The
[frozen source and binary](native_freeze.json) contain no known row, seed,
pair output, or scalar in the public search path. The positive and negative
residuals are separate diagnostic inputs, and [native controls](native_controls.json)
agree with the Sage classifications.

## Measurements and outcome

| Stage | Frozen input and observation | Result |
| --- | --- | --- |
| Sage polynomial filter | Known valid row residual | Accepted, degree-one gcd, exact group witness; 10.302 s norm build and 30.124 s gcd |
| Sage polynomial filter | Deterministic fixed-Q prefix residual `(0,0)` | Rejected, gcd degree zero; 2.467 s norm build and 23.281 s gcd |
| Sage probe phase | Five cases planned; 110-second alarm starts after setup | Two cases completed; `TIME_CAP`, 136.704 s total job |
| Native batched filter | Same two residuals, diagnostic run | Correct classifications; 0.098 ms and 0.134 ms per control |
| Native public search | Frozen source, input, 120-second online cap, one worker | **`ONLINE_TIME_CAP`** after 75,264 residuals in 120.154 s; zero x hits and no row |

The Sage job spent 6.434 s loading/building its exact domains and 5.222 s
constructing `F3`, both outside the per-residual figures. The 110-second
alarm in `run_sage.py` starts after these setup stages; the protocol calls
it a job limit, which overstates what was enforced. Its retained total time
is the operative wall-time record. This mismatch cannot turn the censored
result into a successful gate. Another 58.874 s of the total is not broken
out by the source's phase timers; it includes exact witness extraction and
control checks. It must not be treated as zero in any end-to-end estimate.

The native public run's sustained rate was about 626 residuals/s, or
1.596 ms per residual, well below the isolated diagnostic rate. The host
lacks a CPU isolation receipt, so both rates are exploratory. The public
search result is authoritative for this frozen 120-second gate: it did not
reach a valid row. The [Q1448 reference](../q1448_pair_bloom/RESULT.md) found
a row after 513,088 first-two-pair residuals with the same ordered domains,
but paid a 1,956-by-1,956 target-independent group-sum build. This method
removed that builder and did not reach that reference row within the cap.

The [N131 transfer check](transfer_gate.json) fails before an N131 query.
The exact same-rotation W18 policy has at least 34,448,654,064 distinct-column
pair states **per domain**. This native source materializes each domain. Even
an unrealistically compact one-bit-per-state explicit list needs
4,306,081,758 bytes for a single domain, exceeding 4 GiB by 11,114,462
bytes before coordinates, pair witnesses, indexes, or the other domains.
This is a source-bound failure of this literal materialized-list method;
it does not exclude streaming or symbolic pair generation.

## Checks and limits

The [receipt verifier](verification.json) checked the source and binary
hashes, frozen N41 input, saved checked-Sage runtime, prior independent Sage
row audit, identical positive/negative residuals, native diagnostic outputs,
public search cap, and N131 arithmetic. The native positive hit also passes
an exact group-point lookup. The sampled negative has a degree-zero Sage gcd,
which proves no x-pair completion in the two free domains for that residual.
The public search yielded no row to replay independently.

Two preflight errors preceded the retained run: the installed N41 Sage
field has no `fetch_int` method, and a different saved pair-domain file
stores preimages in the transformed `u=(x+1)^-1` coordinate. The final Sage
source decodes the polynomial basis explicitly and constructs exact pair
outputs directly from the hashed native input. The preflight failures were
not counted as measurements.

No ECC2K-130 ordinary relation or discrete logarithm was found, and no IC
versus rho comparison was run. The negative result narrows the proposed
target-coupled direction: this explicit-domain implementation gives exact
early pruning on N41 controls, but its sustained public search misses the
N41 time gate and its materialized N131 lists exceed the memory gate. A
surviving variant must generate or eliminate pair-output families without
constructing the full W18 pair domains.

## Reproduction

The Sage startup receipt was saved with the repository launcher before the
job. From the repository root, use `./sage --runtime-info` to check the
accepted build and `./sage -python` to run `run_sage.py`. Both first-run
producers refuse to overwrite their result files. Compile `native_batch.cpp`
with the command in `native_freeze.json`, then run its `diagnostic` mode with
`native_control_input.txt` or its `search` mode with the hashed native
input. `transfer_gate.py` and `verify_receipts.py` are standard-Python
receipt checks. Preserve the existing outputs before replaying a first-run
producer.
