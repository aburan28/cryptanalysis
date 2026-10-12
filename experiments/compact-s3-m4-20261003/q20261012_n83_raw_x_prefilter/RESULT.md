# Q1512: raw-x prefilter removes over 30.9 million canonicalizations per N83 scan

A 32 MiB Bloom filter over the **15,488,796 raw x coordinates** of the exact
signed-Frobenius base reduced full-scan canonical Frobenius key calls from
**30,977,592 to 55,639** on one frozen ordinary N83 complement and to
**55,701** on a second. This is a **9.12-bit reduction in that named
operation count**. The filter preserves exact acceptance: Bloom positives
still pass the original canonical-key set and full group replay. The two
ordinary full scans and the baseline used identical inputs and produced
identical raw-x checksums and zero exact-base hits.

| Frozen ordinary complement | Bloom | Canonical key calls | Scan seconds, exploratory | Setup + scan seconds, exploratory | Peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Selected `2eb250a29072` | off | 30,977,592 | 7.188 | 7.607 | 1,249,771,520 B |
| Selected | 16 MiB, 4 hashes | 579,270 | 2.420 | 3.121 | 1,266,532,352 B |
| Selected | **32 MiB, 4 hashes** | **55,639** | **1.966** | **2.749** | **1,283,309,568 B** |
| Holdout `394256b9f901` | off | 30,977,592 | 7.092 | 7.508 | 1,249,771,520 B |
| Holdout | 16 MiB, 4 hashes | 579,183 | 2.844 | 3.555 | 1,266,581,504 B |
| Holdout | **32 MiB, 4 hashes** | **55,701** | **2.171** | **2.949** | **1,283,358,720 B** |

The 32 MiB filter gave **3.66× and 3.27× exploratory scan-wall ratios**,
or **2.77× and 2.55× including its build**. These are same-host
diagnostics without a CPU isolation receipt. Peak RSS rose by about 32 MiB.
The filter build cost **61,955,184 bit sets**; its full scans cost
38,950,595 and 38,947,422 Bloom bit probes. Those operations and the
remaining canonicalizations must be included in a CPU or instruction-count
projection. The native kernel's batch field multiplication and inversion
counts did not change.

## Exact instance and search

The curve is `EC1N83Ckb1h876c2921cb64`. The W≤5 projected base has
**B=30,977,592** distinct subgroup-usable points before sign/Frobenius
folding and **K=186,612** columns; its enumerated-set SHA-256 is
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
There is no isogeny transport. Q1512 is a `PDP4hybrid` stage proposal with
`candidate_id` and `run_id` null; the two ordinary workload IDs appear in
the table. Each full cell scans all B signed second leaves for one exact
first-pair complement.

The parameter screen used the same selected complement for 2,000,000
positive base points (4,000,000 signed candidates) per cell. It tested
8, 16, 32, and 64 MiB at four hashes, plus 16 and 32 MiB at six hashes,
against an unfiltered cell. All seven cells completed with identical
raw-x checksums and zero exact-base hits. The 32 MiB four-hash setting was
promoted alongside 16 MiB four-hash to complete scans on both frozen
complements. The [frozen protocol](protocol.json) specifies those cells
and their order; [result.json](result.json) retains every native counter,
wall interval, peak RSS, command, exit status, and stdout.

The exactness invariant follows from the construction: the filter inserts
the raw x of every Frobenius shift of every base orbit representative.
Signs share x. Any x whose canonical key belongs to the factor base is
therefore one of the inserted raw values and passes the filter. Bloom
false positives still undergo the original exact key lookup. The
first-orbit controls and the [deep-orbit controls](deep_control.json)
exercise both signs and a noninitial orbit at Frobenius shift 37; each
positive control produced the same group-checked hits with and without
the filter. [validate.py](validate.py) checks source and binary hashes,
ordinary outputs, controls, and [analysis.json](analysis.json).

## Degree-131 work boundary

This change removes most canonicalizations, but it still scans every base
point. On the exact N131 W≤6 base, Q1505's one-complete-four-sign-scan
formula stays **65,596,347,880 = 2^35.933 batch multiplication calls**,
excluding inversion internals. Its independent-uniform-first-pair
relation-supply model remains **2^123.289 such calls**, 62.289 bits above
an abstract 2^61 call reference. Those figures are a specified scan-route
model, not the complete N131 solve. Using the same 17.33 Bloom bits per
unique x at N131 would require a power-of-two filter of **8 GiB** for the
3,279,817,394 projected raw x values; construction and memory traffic
would need separate measurement. The fully charged N131 single-target
operation exponent is still unset because this filter does not establish
ordinary relation yield or rank novelty.

The next solver step remains target-conditioned **second-pair selection**
that avoids a complete B-point scan. This prefilter is an exact and faster
membership component for that search; benchmark its CPU effect on an
isolated host before promoting wall-time gains.

The frozen measurement binary is pinned by SHA-256 in the protocol. A
source rebuild with the same command produced a different Mach-O byte hash
and UUID; its two signed deep-orbit controls and one ordinary 2-million-pair
screen matched the frozen binary's hit, checksum, canonicalization, and
Bloom-probe counters exactly. The [rebuild check](rebuild_check.json) records
both hashes and outputs. Rebuild and check the source behavior on ARM64:

```sh
clang++ -O3 -std=c++17 -DECC2K83_ORBITS=186612 -DECC2K83_FAST_KEYER \
  experiments/compact-s3-m4-20261003/q20261012_n83_raw_x_prefilter/native_prefilter.cpp \
  -o /private/tmp/q1512-rebuild
PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_n83_raw_x_prefilter/check_rebuild.py /private/tmp/q1512-rebuild
```

Validate the original frozen measurement with its recorded binary at
`/Volumes/SSD990/llm/tmp/q1512-native-prefilter`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_n83_raw_x_prefilter/validate.py
```

The [build receipt](build_receipt.json) records the compiler, included
source hashes, and frozen binary hash. Run [run.py](run.py) in a new output
directory for a repetition; it refuses to overwrite this result.
