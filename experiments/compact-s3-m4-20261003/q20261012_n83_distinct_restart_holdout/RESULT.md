# Q1498: 208-flip distinct-pair yield repeats on an ordinary N83 holdout

The eight Q1497 masks selected by **distinct** usable first-pair work were
frozen before replay against workload `394256b9f901`. All eight runs reached
the first S3 pair within the 45-second CPU and 90-second wall caps. Their
exact Q1495 classifications match the selected point phase by phase: four
distinct usable pairs among eight distinct outputs.

| Workload | Runs | Distinct usable first pairs | Charged CNF/XOR calls | Calls per distinct usable pair |
| --- | ---: | ---: | ---: | ---: |
| selected, `2eb250a29072` | 8 | 4 | 769,426 | 192,357 = 2^17.553 |
| holdout, `394256b9f901` | 8 | 4 | 788,018 | 197,005 = 2^17.588 |

The holdout costs 2.42% more calls per distinct usable first pair. These are
ordinary N83 first-pair stage costs, with both successful and rejected
attempts charged. The eight-mask sample leaves substantial uncertainty in
the population yield: four in eight has a 95% Wilson interval of
0.215–0.785. The selected and holdout point classifications use the same
masks and should not be counted as 16 independent Bernoulli trials.
[Protocol](protocol.json), [freeze](freeze.json),
[run receipts](runs), and [result](result.json) bind the same binary, masks,
input archives, exact base predicate, and output hashes. The result keeps
`candidate_id` and `run_id` null, `PDP4sat`, and `isogeny: "none"`.

The next experiment must turn distinct first pairs into verified complete
four-summand relations and measure rank novelty. Until then the fully
charged N131 exponent remains unset.
