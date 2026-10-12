# Q1472: exact SAT work meter for the chained-S3 solver

Q1472 adds CaDiCaL's exact `propagations` statistic to Q1466's native
four-summand solver. The [audit](archive_audit.json) verifies that the
source differs from Q1466 only in the statistic read, availability check,
JSON output, and identifying comment. The exact Q1467 N53/N83 CNFs,
targets, factor bases, decision policy, 250,000-pair admission cap,
1,000,000-conflict cap, and 60-second native wall cap are reused. The
[protocol](protocol.json) was committed before the six runs and binds the
binary, inputs, checked Sage runtime, and source hashes. This remains a
`PDP4hybrid` stage proposal with `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`.

N53 uses `EC1N53Ckb1hf77aab617904`, actual factor base `B=2,756`,
26 signed-Frobenius columns, and enumerated-set digest
`cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70`.
N83 uses `EC1N83Ckb1h876c2921cb64`, the exact W≤4 base with
`B=1,934,066`, 11,651 columns, and digest
`1b4110f055c88a4b1be2bfdd4bdb1cfca62bc41f49f0a5cac7698f7d4fc35325`.

| Frozen cell | Native result | Verified relation | SAT propagations | SAT conflicts | Field mul / sqr / inv calls | Exploratory process wall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| N53 planted, pinned | SAT | 1 | 82,352 | 0 | 209 / 1,236 / 18 | 0.310 s |
| N83 planted, pinned | SAT | 1 | 294,580 | 1 | 258 / 2,180 / 20 | 0.383 s |
| N53 planted, unpinned | capped | 0 | 273,086,668 | 71,128 | 17,108,600 / 72,334,266 / 8,379 | 60.448 s |
| N83 planted, unpinned | capped | 0 | 309,788,583 | 44,996 | 554,933 / 3,984,876 / 18,828 | 60.434 s |
| N53 ordinary | capped | 0 | 297,449,277 | 75,355 | 17,049,276 / 72,071,211 / 8,381 | 60.393 s |
| N83 ordinary | capped | 0 | 315,503,020 | 45,255 | 533,667 / 3,810,632 / 17,456 | 60.472 s |

The two pinned models independently replay as four-point relations. The
other four cells preserve failed search work and have no verified relation.
At their caps, the ordinary queries spent about `2^28.148` N53 and
`2^28.233` N83 **SAT propagations**, respectively. These are exact counts
in a named solver unit for censored attempts, not solve-cost exponents.
CaDiCaL's statistic covers its work through termination, including initial
propagation. The field multiplication, squaring, and inversion counts are
separate units. They cannot be added to SAT propagations or converted to
seconds without a declared calibration. Wall times are exploratory because
the host lacks an isolation receipt.

Q1470 showed that SAT conflicts could grow at N83 while field primitive
calls stayed fixed. Q1472 confirms that SAT work can be recorded directly,
but a successful unpinned N83 decomposition and natural N83 relation yield
are still missing. No N53-to-N83 successful-solve growth fit or complete
N131 `2^x` follows. Base construction, relation collection to full rank,
final matrix work, target descent, and scalar replay also remain uncharged;
the challenge gate stays closed.

## Reproduce

```sh
python3 experiments/compact-s3-m4-20261003/q1472_sat_work_meter/build.py --check
python3 experiments/compact-s3-m4-20261003/q1472_sat_work_meter/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1472_sat_work_meter/audit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The [runner](run.py) refuses to overwrite receipts. Each run's native
stdout, stderr, model when found, and source-bound receipt are under
`runs/`.
