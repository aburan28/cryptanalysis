# Q1429: weight-unsaturated partial-pair feasibility

Q1428's bilinear-span condition was sound but its frozen samples had
already filled each leaf's weight bound. This follow-up leaves one or two
possible one bits on each partial leaf. It compares the span condition
against exact enumeration of all permitted first-leaf completions and
their `S3(a,m,b)=0` partner roots. A span rejection must imply that exact
enumeration finds no partner; a span acceptance does not imply a partner.

The [frozen protocol](protocol.json) uses exact type-II normal fields at
N53, N83, and N131. It names the N53/N83 Q1427 curve and factor-base
records and the exact N131 W≤6 Q1413 base from Q1425's support screen.
The field intermediate is sampled uniformly and independently of any
target. Partial leaves have exactly `w-slack` fixed one bits in a prefix;
the last `k` coordinates remain free, with `slack` equal to one or two.
The screen records rank, sound rejections, the exact completion-domain
size, exact root calls, and any witness. It does not check curve lifting
or subgroup base membership; a pair found here is only an x-coordinate
`S3` witness.

The purpose is to decide whether adding this necessary-condition filter
to the four-point solver could save work before a leaf is complete. The
root-call and bilinear-column counts have different costs and must not
be treated as equivalent operations. Synthetic uniform intermediates
do not measure ordinary relation yield or a complete N131 solve.
The stage is proposal `Q1429`, with `candidate_id: null` and
`isogeny: "none"`.

## Reproduction

Use the checked repository Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1429_unsaturated_span/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1429_unsaturated_span/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1429_unsaturated_span/run_screen.py --check
```
