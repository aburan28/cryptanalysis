# Q1524: one batch inversion serves four N83 complements

Jointly batching four signed complements reduces the exact N83 second-pair scanner from **121,008 to 30,252 field inversions** at a 512-pair batch size, while preserving every Q1521 per-complement hit count, exceptional count, Bloom count, canonical-key count, and x-key checksum. One pinned positive control returned four independently group-replayed hits. Both frozen ordinary public points completed all four complements with zero exact-base hits, as in Q1521.

The four-complement group still performs **309,775,920 field multiplication calls outside inversion** and **123,910,368 squaring calls outside inversion**. The pinned N83 Itoh–Tsujii `inv()` uses eight multiplication and 82 squaring calls per inversion: its six loop iterations each multiply once; the two set lower bits in 82 add one multiplication and one squaring each; the `sigma` lengths sum to 79 squarings, followed by one final squaring. Thus the 512-pair setting saves **726,048 multiplication and 7,441,992 squaring calls inside inversion**, or 0.234% of the baseline multiplication-call total at this stage. The ordinary scan has zero hits and zero equal-x exceptions, so these exact counts need no exceptional-path adjustment.

| Joint batch size | Inversions per four complements | Selected child CPU s | Holdout child CPU s | Selected / holdout wall s | Exact Q1521 output match |
| ---: | ---: | ---: | ---: | ---: | --- |
| 512 | 30,252 | 9.24 | 9.74 | 15.44 / 17.42 | Yes / yes |
| 2,048 | 7,563 | 10.60 | 10.13 | 48.74 / 34.86 | Yes / yes |
| 8,192 | 1,891 | 10.95 | 10.90 | 61.44 / 66.58 | Yes / yes |

Q1521's separate 512-pair baseline took 11.11 and 10.39 child CPU seconds on the same selected and holdout inputs. The ordinary host lacks a host-level isolation receipt, and the wall observations show strong contention. The exact inversion reduction is an algorithmic result; CPU ratios and the 512-pair ranking are exploratory. Increasing the batch size monotonically reduces inversion calls but did not improve observed child CPU time in these runs. Peak child RSS was about 1.28 GB, in the same range as Q1521.

The exact curve is `EC1N83Ckb1h876c2921cb64`; its cofactor-four weight-at-most-five base has **B=30,977,592** distinct usable subgroup points, **K=186,612** signed-Frobenius columns, and point-file SHA-256 `56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`. This is `Q1524`, `PDP4hybrid`, with null candidate and run IDs and `isogeny: "none"`. The [protocol](protocol.json), [batch screen](batch_screen.json), [build receipt](build_receipt.json), [raw receipts](runs), and [validator](validate.py) fix the source, included native arithmetic, binary, inputs, resource caps, status, and output comparison. The first wrapper compile failure is retained separately in [pre_driver_failure.json](pre_driver_failure.json); no solver run used that draft.

The two ordinary points supplied **zero verified relations and zero novel rows** in this panel. Cost per useful relation remains censored. Q1505's conditional N131 independent-first-pair relation-supply model remains **`2^123.289` batch multiplication calls excluding inversion internals**, 62.289 bits above an abstract `2^61` reference in the same unit. Q1524 reduces an inversion component of a full scan but does not change that model's multiplication boundary or fill its missing rank, final matrix, target descent, and replay costs. The fully charged N131 exponent remains unset. The next solver experiment should reduce the number of second-base points examined per complement or enrich ordinary relation yield; another batch-size reduction cannot close a 62-bit model gap.

Recheck the exact seven-row panel with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1524_joint_inverse/validate.py
```
