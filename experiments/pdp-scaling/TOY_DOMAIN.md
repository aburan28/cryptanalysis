# Explicit toy-domain filtering follow-up to PR #45

## Change and scope

Profiling the previous incremental S3 chain on n=7,l=4, phases (0,1,2),
seed 17 found 24 rejected polynomial models and approximately 96% of its
charged PDP CPU time in SAT calls. Lifting/subgroup validation was happening
after SAT search. This experiment supplies exact admissible payloads before
search, so SAT can propagate their restrictions immediately.

`ToyDomainTemplate` builds the original circuit, then enumerates the nonzero
payloads of V, lifts each x to E0, and checks `[r]P=O`. The resulting allowed
payloads apply to each Frobenius-transformed block: E0 and the order-r
subgroup are Frobenius-invariant. Positive support selectors encode the
allowed set; exactly one selector follows from at-least-one plus its payload
bit implications (distinct selectors imply conflicting assignments).

The filter contains no target, pair sums, target decomposition or oracle
answers. The independent exact point oracle remains instrumentation only.
Final rational lifting, subgroup checks, signs and actual point addition
are unchanged. The all-invalid domain produces an explicit contradiction.

**This is an exponential preprocessing control:** enumeration costs 2^l
payload checks. It is explicitly limited to odd n<=19 and l<=8. It is not
an efficient algebraic membership construction at cryptographic sizes, an
implementation of the 26-bit factor space, a Gröbner speedup, or a full-DLP
speedup. The production solvers and the original benchmark defaults are
unchanged. The original baseline remains available through `Template`.

## Measurement contract

Compare the previous incremental S3 chain with two guessed payload bits
against the same solver plus the new domain constraints. Measure both
freshly in this runtime. Every campaign starts cold; the filter enumeration,
point checks, construction, loading, failed searches and verification are
charged in total PDP CPU. Reuse within a campaign is eight targets at n=7
and four at n=13. The original exclusion for independent corpus/oracle
instrumentation remains recorded separately.

The fixed grids are (n,l)=(7,4) and (13,6), phases (0,0,0)/(0,1,2), seeds
17/911, three repetitions. Seed 911 is the held-out corpus. Targets are
identical between contenders and unique up to sign within each campaign.
Order alternates between baseline-first and candidate-first. Search budget
is one second per target including all guesses. Each configuration retains
all statuses; a timeout is not a negative answer or a completed runtime.
No cost ratio is emitted unless **both versions finish every target** with
matching oracle verdicts. This prevents a partial completion from masquerading
as an equal-work speedup. None of these decompositions measures relation rank.

Acceptance: zero incorrect answers, at least 20% lower median total PDP CPU
on each n=7 seed/phase workload at equal completions. n=13 is a completion
probe, not a speed claim when the baseline times out. No exponent is fitted.

## Reproduce

```sh
cd experiments/pdp-scaling
python3 -m pip install pycryptosat==5.16.0
python3 -m unittest -v test_fixed_phase.py test_toy_domain.py
python3 toy_domain_bench.py --repetitions 3 --out /tmp/toy_domain_matched.json
```

The runner refuses to overwrite results and records source hashes, versions,
base commit, input hashes, witnesses, domains and exact per-target outcomes.
The domain tests exhaust every source payload at every tested phase, check
both encodings throughout the order-29 subgroup, replay reversed/negated
targets, test empty domains, and exercise positive/negative n=13 cases.

## Results

Fresh paired results (three repetitions per seed/phase):

- n=7,l=4: median total PDP CPU is **9.24–15.99x lower** than the previous
  incremental chain, depending on seed and phase pattern. Both versions
  correctly decide all 96 variant-target attempts, with 18 verified positive
  outcomes each. All four n=7 seed/phase workloads pass the engineering gate.
- n=13,l=6: baseline decides **1/48** attempts; candidate decides **32/48**,
  including three verified positive outcomes. Sixteen candidate attempts
  remain unresolved. These counts pool repetitions, not distinct targets.
  No equal-work speed ratio is claimed for n=13.
- The admissible source domains contain one payload at (7,4) and four at
  (13,6). That unusually small valid domain explains much of the gain; it
  cannot be extrapolated to a large factor base.

See [results/toy_domain_summary.md](results/toy_domain_summary.md) and the
adjacent raw JSON. These results are **engineering stage diagnostics**.
The next scalable question remains how to enforce admissibility cheaply
without enumerating the factor base. Passing this test alone does not
answer that question or remove the need for the full rho comparison.
