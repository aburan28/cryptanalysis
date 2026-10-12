# Q1431: guarded partial-pair span propagation

Q1430 showed that the target-conditioned four-summand SAT trail reaches
partial second-pair leaves where Q1428's linear-span condition can reject a
state. Q1431 adds that condition as an external CaDiCaL propagator. It keeps
the Q1430 CNF, target list, exact N53/N83 curve and factor-base identities,
decision policy, controls, and 60-second/one-million-conflict limits. Its
[frozen protocol](protocol.json) was committed before ordinary runs.

For fixed second-pair intermediate `m`, write the partial leaves as
`a = a0 + Σ u_i e_i` and `b = b0 + Σ v_j e_j` in the declared normal basis.
In characteristic two,

```text
S3(a,b,m) = c + Σ u_i α_i + Σ v_j β_j + Σ u_i v_j γ_ij
c       = S3(a0,b0,m)
α_i     = e_i²(b0²+m²) + e_i b0 m
β_j     = e_j²(a0²+m²) + e_j a0 m
γ_ij    = (e_i e_j)² + e_i e_j m.
```

The Boolean products `u_i v_j` are relaxed to independent span
coefficients. If `c` lies outside the resulting `F2` span, no completion of
the partial pair can satisfy `S3=0`. The solver then emits one clause
guarded by **all** fixed bits of both leaves and **all** bits of `m`. That
clause excludes exactly the impossible fixed assignment and every extension
of it. It does not depend on curve lifting or the sparse-weight rule, so
those additional restrictions cannot invalidate the rejection. The native
solver checks that every guard literal is false on the current assignment.

The filter runs only when both leaves are partial, each has one or two
weight units left, and each has at most 14 free bits at N53 or 20 at N83.
It memoizes checked partial states. It retains the first 16 rejection
snapshots for independent replay. The [native-versus-Sage validation](span_validation.json)
matches rank, span membership, and columns tested on 112 cases: archived
ordinary trail states, synthetic partial states, and completions of two
independently verified four-point witnesses. The witness cases had zero
false rejections. Q1428's separate N3/N5 exhaustive test checks the algebra
and soundness on small fields.

The stage remains proposal `Q1431`, with `candidate_id: null` and
`isogeny: "none"`. The `PS1...PDP4theory...` labels identify this solver
stage, not a complete `IC1` candidate. The manifest records actual usable
factor-base points `B`, folded columns `K`, and enumerated-set digests
separately.

## Frozen N53/N83 result

The [four-cell verification](verification.json) replays both known-witness
controls and the first emitted rejection snapshots. Both controls return a
verified four-point relation. Both unpinned ordinary cells remain censored
at the 60-second wall cap, with no verified relation.

| Degree | Cell | Verified relations | Span checks / rejections | Reverse pair-1 calls | Filter field multiplies | Total field multiplies | Matched Q1430 total multiplies |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 53 | Freed-partner control | 1 | 0 / 0 | 1 | 0 | 283 | 283 |
| 53 | Ordinary, 60 s cap | 0 | 213,296 / 206,090 | 12,020 | 67,632,400 | 68,182,727 | 4,764,022 |
| 83 | Freed-partner control | 1 | 0 / 0 | 1 | 0 | 307 | 307 |
| 83 | Ordinary, 60 s cap | 0 | 67,018 / 66,457 | 19,354 | 53,520,040 | 54,467,127 | 3,676,888 |

The filter cuts the reverse-root loop in these censored prefixes, but its
rank calculation rebuilds millions of bilinear columns. Within the same
wall cap, total multiplication calls are about 14.3 times Q1430 at N53
and 14.8 times at N83. The solvers follow different search paths, and this
host lacks a CPU isolation receipt, so those numbers are algorithmic
diagnostics rather than a controlled wall-time speed ratio. Filter work,
clause production, and memory are retained in the receipts. There is no
measured cost per useful relation or natural relation yield. The complete
N131 `2^x` remains unknown.

## Next gate

The bilinear column `γ_ij` depends on `m` and the two free-coordinate
indices, not on the fixed leaf values. The archived ordinary runs activate
the final-root link once and reuse very few values of `m`. Precompute or
incrementally cache these columns per exact `m`, charge cache construction
and memory, and repeat the same frozen ordinary targets. A useful result
must reduce **total** charged work or find an independently verified
ordinary relation; a lower reverse-root count alone does not pass.

## Reproduction

From the repository checkout:

```sh
python3 experiments/compact-s3-m4-20261003/q1431_guarded_span/build_binaries.py --rebuild
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1431_guarded_span/validate_span.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1431_guarded_span/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1431_guarded_span/verify_archive.py --require-complete --emit
```

`run_stage.py` refuses to overwrite archived cells. The accepted Sage
runtime receipt was saved before the measured runs. CPU timing remains
exploratory without the repository's isolation gate.
