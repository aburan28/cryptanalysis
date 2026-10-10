# Sparse normal-basis canonicalization on the N53 indexed S3 path

## Controlled change

The reference is an exact copy of the N53 shared-inversion, sharded S3
index source used by the canonical-root Bloom experiment, without its Bloom
screen. The candidate copies that source and replaces the 53-rotation
normal-basis canonicalizer with the existing longest-cyclic-zero-gap
algorithm from `crypto/examples/koblitz_orbit_dlp_slice_ic_fastindex4.rs`.
Both index insertion and target-time lookup use the candidate canonicalizer.
The returned canonical key **and** minimum shift must equal the reference;
the shift determines the recovered four-point witness. No Bloom filter is
present in either variant in this experiment.

## Frozen correctness and measurement plan

- Curve and public target: `EC1N53Ckb1h888961ed110e`, Koblitz `a=0,b=1`
  over `F_2[x]/(x^53+x^6+x^2+x+1)`, subgroup order
  `21,044,858,204,113`, point `[6825828048296061,3029097503049988]`.
- Workload `Wc3929365e014`: 25,864 usable factor-base points, 244 folded
  columns, relation seed `20260928`, 14 index/relation workers plus main,
  and one supplied public point in each fresh process.
- Before timing, test every normal-basis word for degrees 1 through 13,
  including all 8,192 N13 values, for exact `(key, shift)` equality. Guard
  zero-run levels whose shift would exceed the field degree. Test 50,000
  deterministic N53 words, including
  all-zero, all-one, and sparse/dense edge patterns. On the actual N53 index,
  compare `(key, shift)` on a deterministic sample across its state range.
- Build release reference and candidate in this directory's own Cargo target
  directory. Freeze source, dependency, protocol, workload, and binary SHA-256
  before target runs. Record disk space before and after build.
- Run five fresh-process alternating pairs: `reference/candidate`,
  `candidate/reference`, `reference/candidate`, `candidate/reference`,
  `reference/candidate`. A process receives the same point, seed, worker
  count, and 30-second process wall cap. Preserve raw outputs, failures, and
  order. The online clock starts after reusable base/index preparation and
  ends after scalar replay. Retain all exclusive online phases and setup
  timing, rather than averaging setup into target time.
- The semantic equality gate compares target witness, ordered relation
  witnesses, attempt count, target-span stop, rank, and recovered scalar.
  Independently replay the first pair's point and relation equations in the
  repository's checked Sage build, with runtime info saved beforehand.
- This host lacks an audited CPU isolation receipt. Report wall ratios as
  exploratory and leave controlled speedup unknown. A disjoint-point panel
  and the isolated benchmark service are promotion gates.
