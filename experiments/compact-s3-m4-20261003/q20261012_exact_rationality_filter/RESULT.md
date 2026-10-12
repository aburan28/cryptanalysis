# Q1495: exact base-membership predicate cuts N83 filter field calls by 13.93 times

For the declared normal-basis weight bases, a nonzero leaf x belongs to the
usable factor base exactly when

`trace(x^(-1)) == (HammingWeight(x) mod 2)`.

The predicate agrees with curve lifting on **all 24,857** nonzero N53 masks
of weight at most three, identifying 12,031 rational x masks. Across all
**373,101** N83 Frobenius orbit representatives of weight at most five, it
identifies 186,612 rational orbits, exactly the enumerated base column count.
The frozen base manifests record zero identity projections and zero duplicate
projected orbits in both cases. Thus every rational x in these two declared
domains contributes a usable base point; the predicate is specific to these
exact curves, bases, and cofactor policies.

For `E: y^2 + xy = x^3 + 1`, write `y = xz` at nonzero x. The curve equation
becomes `z^2 + z = x + x^(-2)`, which has a binary-field solution exactly when
the right-hand side has trace zero. Trace is invariant under squaring, and the
trace of a normal-basis x is its coordinate-weight parity. This yields the
stated test with one inverse and one trace; the implementation stops after
the first rejected leaf.

| Exact domain or sampled boundary | Short predicate | Full lift/project/key filter | Ratio |
| --- | ---: | ---: | ---: |
| N53 x masks checked | 24,857 | 24,857 independent curve-lift checks | exact agreement |
| N83 x orbits counted | 373,101 | frozen base has 186,612 rational orbits | exact count agreement |
| N83 Q1494 first-pair set, 40 pairs | **427** CountedOnb field API entries | **5,948** CountedOnb field API entries | **13.93× fewer** |

The N83 paired count uses the same 40 Q1494 pair assignments, in their frozen
order, and both predicates accept the same eight usable pairs. These field API
entries cover membership filtering only. WDSat's first-pair CNF/XOR calls,
formula construction, conversion outside the predicate, and later
decomposition work are separate costs. Host wall time is not used as a
speedup claim.

The [protocol](protocol.json) fixes the N53 and N83 curve IDs, actual base
sizes, folded column counts, and cost boundary. The [freeze](freeze.json)
binds both base records, N83 packed point keys, Q1494 receipts, and source
files. The [result](result.json) retains per-weight counts and all 40 paired
operation vectors. The [validator](validate.py) checks the frozen identities,
base counts, sampled pair classifications, and exact operation vectors.
Q1495 is a `PDP4sat` stage proposal with null IC candidate/run IDs and
`isogeny: "none"`.

The next implementation gate is to apply this exact predicate at WDSat's
first complete leaf assignment, reject unusable pairs before continuing the
middle-root search, and measure whether that changes work per **usable**
first pair on fresh N53/N83 ordinary inputs. The fully charged N131 one-target
exponent remains unset until second-pair completion, useful-relation yield,
rank, matrix work, target descent, and replay are measured.

    env PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_exact_rationality_filter/validate.py
