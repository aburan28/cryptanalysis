# Packed target coefficients for exact cutset queries

This experiment replaces target-by-target Python ANF row construction and
ctypes repacking in the grouped cutset query with a reusable packed buffer.
The last S3 equation is affine in each target bit over GF(2): its zero-target
coefficient vector and nine bit deltas determine every target vector exactly.
The packed arm combines those deltas into the same monomial order used at
layout construction, writes fresh offsets and terms into reusable native
buffers, and calls the unchanged native cutset branches. It does not retain
target answers. The direct arm builds the S3 ANF and allocates packed arrays
for each target. Both arms share one set of static branch layouts and perform
the same original S3 field-equation evaluation, static ANF checks, and curve
point replay inside the complete target interval.

Freeze two GF(2^9), curve `b=1`, seed-1 cases: four and five summands with
seven-bit abscissae. Keep the 24-variable maximum bag and 200,000,000-state
per-branch cap. The four-summand case has two cutset branches, the
five-summand case four. Use the exact source-bound grouped-factor optimized
and UBSan libraries. For every target abscissa `0..511`, compare the packed
rows to independently generated and modulo-two-canonicalized S3 ANF rows;
compare each arm's every branch status to the independently enumerated
branch-restricted curve-sum set; and check every SAT witness against its
original static and target ANF rows, the original S3 field equation, and
curve point replay. Record all UNSAT, inconclusive, failure, and cap rows.

The complete target interval starts before fresh target coefficient
construction and ends after all native branch solves and the shared field,
static-equation, and point checks. Static layouts, target-bit templates, and
independent curve enumeration are target-independent setup. The validation
driver separately constructs the original target ANF after each paired query
for the row-byte and SAT-witness audit; this audit is outside both matched
query intervals. Exactly 4,096 primary queries and 12,288 native branch
queries are expected: two cases, two builds, 512 targets, and two arms.

For the exploratory complete-query timing panel, use the optimized build,
three target warmups per arm (`0`, `1`, `161`), then three full 512-target
passes per case. Alternate direct/packed arm order by target and repetition.
Retain all 6,144 timed query rows and 18,432 native branch rows, including
failures. Compare paired target intervals and their coefficient, native, and
check phases; calculate uncertainty by resampling target abscissae as
clusters, keeping their three repetitions together. A CPU speedup claim
requires the separate physical-host isolation receipt. The engineering
target of 2x is a hypothesis, not an acceptance substitution for correctness.

Run the source-bound grouped-factor build chain in
`.github/workflows/groebner-f6-cutset-packed.yml` and then the validation
driver from a clean committed checkout:

```sh
python3 experiments/groebner-f6-cutset-packed-20261009/validate.py \
  --output /absolute/path/to/new-evidence-directory
```
