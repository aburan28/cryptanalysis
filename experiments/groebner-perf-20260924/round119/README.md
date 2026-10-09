# Bounded grevlex bitset normalization in certified F4

This opt-in candidate represents a polynomial being normalized as a 4096-bit
set when every monomial in that call uses only the low 12 variable bits. Its
per-query rank table orders those monomials in the same descending grevlex
order as the sparse `round118` kernel. Reducer priority remains stable by row
length and installation order; each reducer multiplication toggles monomial
bits with Boolean parity, then XORs the current row. Proof nodes and semantic
work charges retain their original order. Wider-support calls use the
`round118` scratch-buffer path.

This experiment tests whether avoiding repeated sort and vector merge work
inside normalization reduces the native F4 phase and the complete certified
point-decomposition query. The five frozen 12-variable queries are paired
against the scratch-buffer candidate with one warmup and five alternating
AB/BA repetitions each. The optimized and UBSan panels require independently
audited proof and curve replay. Exact 21-, 32-, and 64-variable controls must
pass and reject proof corruption. The source and build receipts are frozen
before timing. CPU wall ratios on the local contended host are diagnostics;
promotion requires a qualifying isolated-host receipt.

Run through the same source-matched reference used by `round118`:

```sh
python3 experiments/groebner-perf-20260924/round119/build.py \
  --reference-root /absolute/source-matched/reference
GROEBNER_F4_REFERENCE_ROOT=/absolute/source-matched/reference \
  python3 experiments/groebner-perf-20260924/round119/panel.py \
  --reference-report /absolute/audited/round112/panel/report.json \
  --output /absolute/new/bitset-panel
GROEBNER_F4_REFERENCE_ROOT=/absolute/source-matched/reference \
  python3 experiments/groebner-perf-20260924/round119/test_large.py \
  --output /absolute/new/bitset-large.json
python3 experiments/groebner-perf-20260924/round119/profile.py \
  --reference-root /absolute/source-matched/reference \
  --reference-report /absolute/audited/round112/panel/report.json \
  --output /absolute/new/bitset-profile --reps 5
```
