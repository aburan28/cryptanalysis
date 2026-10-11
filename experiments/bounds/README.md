# Measured bounds of libcryptanalysis

This directory puts the constants `ca_bench complexity` measures on the same
kind of page as ecbench's `docs/bounds/` in aburan28/crypto -- one sealed,
content-addressed record per method, domain and tier, ranked into a frontier
by ecbench's own `frontier build` -- **in this library's unit**, which is not
ecbench's.  The crypto protocol says this is the way to put the two libraries
on one page "without pretending the units agree" (its `docs/bounds/README.md`
§12), and the domain's `unit` field is what keeps them apart: records in
`cryptanalysis.group_ops` and records in `ecbench.gae` never share a domain,
so no frontier ever compares them.

```sh
# from the repository root
build/ca_bench complexity --bits 20,24,28,32,36 --reps 16 --json experiments/bounds/sweeps/complexity-DATE.jsonl
python3 experiments/bounds/emit_bounds.py emit --sweep experiments/bounds/sweeps/complexity-DATE.jsonl
ecbench frontier build --bounds experiments/bounds/records --out experiments/bounds/frontier.json --markdown experiments/bounds/FRONTIER.md
```

[`FRONTIER.md`](FRONTIER.md) is the generated page; `frontier.json` its
machine-readable twin; `records/*.json` the records it was built from;
`sweeps/*.jsonl` the raw measurements they were fitted from.  Nothing here is
edited by hand.

## What a record is

A record is one method of this library (`ca.bsgs`, `ca.rho`, `ca.kangaroo`,
`ca.grumpy`, each a `ca_*_solve` entry point at its default parameters) on
one **domain** -- the whole-group DLP with a single planted target, a group
kind (`zp`: prime-order subgroups of safe-prime `Z_p^*`; `ec_prime`:
prime-order curves over `F_p`), the unit `cryptanalysis.group_ops`, a tier
(`toy` for fields of at most 32 bits, `medium` to 96, `crypto` above, from
`docs/claims-and-verification.md` of crypto-autoresearcher) and the envelope
{one target, no precomputation, one thread}.  Its sizes are the group orders
of the sweep that fall in the tier; a sweep that spans tiers yields one record
per tier, never a mixed one.  The schema is `ecbench.bound/v1`, field for
field as `src/cryptanalysis/ecbench/bounds.rs` defines it:

| field | here |
|:--|:--|
| `domain`, `domain_id` | as above; `ECDOM1h` + 12 hex of the SHA-256 of the domain's canonical JSON |
| `method`, `method_id` | the entry point and its parameters as strings (`auto` where the solver derives a value from the group order); `ECM1h` + 12 hex over `{"schema":"ecbench.method/v1","id":…,"params":…}` |
| `level` | `exponent` with four or more sizes, `constant` otherwise |
| `sizes[]` | one row per group order: `slug` `ca-<group>-<bits>`, `log2_r`, `r`, `field_bits`, the automorphisms the floor counts (2 on a curve: negation; 1 in `Z_p^*`), the floor `sqrt(pi / 2A)`, instances as workloads, runs, verified runs, mean `group_ops`, mean `S = group_ops / sqrt(N)` with its interval, the ratio to the floor, the documented constant (`declared_s`) and its ratio to the floor, table entries per `sqrt(N)`, `uncharged_per_sqrt_r` (0.0, see below), `levels` (`L0` for every run: no isolation was measured and none is claimed) |
| `fit` | `group_ops = C · N^alpha` by least squares on every verified run's `(ln N, ln group_ops)`, one stratum per size; `alpha` with its two-stage bootstrap interval, `log2_c`, `R²`, `declared_alpha` 0.5, whether the interval contains it, and `scaling_claim` |
| `constant` | mean `S` and mean ratio to the floor over all verified runs, with intervals; the documented ratio to the floor when it is one number across sizes |
| `dimensions` | the axes the frontier reads: `ops` (ratio to the floor), `memory` (`ca_stats.table_entries / sqrt(N)`), `uncharged` (0.0) |
| `stages[]` | one stage, `search`, with share 1.0: the library reports a solve as one count |
| `provenance` | one session: the sweep file, named `CAB1h` + 12 hex of its SHA-256, with `spec_id` `CAS1h` + 12 hex over the command line, `env_class_id` `CAENV1h` + 12 hex over the host string, the binary's SHA-256 and the commit from the sweep header, the file's full SHA-256 as `records_sha256`; `audits` is empty |
| `admissibility` | `admissible` when every run of the arm verified its answer, `inadmissible` otherwise; `bounded` false and `unpriced` empty (the unit has no unpriced counters); `deterministic` true |
| `fit_options` | the tier, 2000 resamples, seed 20261005 |
| `bound_id` | `ECBND1h` + 12 hex of the SHA-256 of the record's own bytes with the field empty |

Identities follow the AGENTS.md rule for canonical records -- sorted keys,
compact separators, ASCII escapes, no floats, the first 12 hex digits of a
SHA-256 -- which is also ecbench's (`canonical.rs`); `test_seal.py` checks
that the domain id and method ids of two real ecbench records come out of
this code.  The seal is the Rust `seal_document` byte for byte: the pretty
print is `serde_json::to_string_pretty` with sorted keys plus a trailing
newline, floats in `ryu`'s shortest form.  `test_seal.py` loads the two real
records in `testdata/` (`docs/bounds/records/prime-rho-neg.json` and
`prime-bsgs-neg.json` of aburan28/crypto at `85be1540`), reproduces their
bytes from their parsed form, blanks `bound_id` and recovers
`ECBND1h7b69b9787056` and `ECBND1hd392c8f42bb0`; the same writer reproduced
every record, challenge and frontier of that directory (51 files) when it was
written.  `ecbench frontier build` checks every seal before it reads a value,
so a record this adapter writes is one ecbench would accept or refuse on the
same grounds as its own.

One row of the sweep is one solved instance, keyed by (algorithm, group kind,
field bits, instance), the analogue of AGENTS.md's (candidate, workload, run):
a failed or unverified solve stays a row with `ok: false` and its status, and
makes the record `inadmissible` rather than disappearing.  The IC naming
(`EC1`, `IC1`, `PS1`) does not apply -- these are the generic square-root
solvers, not index-calculus candidates.

## The unit, and why it is never compared with `ecbench.gae`

`cryptanalysis.group_ops` is `ca_stats.group_ops` **as the library counts
it**: every group operation a solver performs through `ca_group_op`,
`ca_group_batch_op` and `ca_group_mul` (a scalar multiplication is counted as
the operations it performs), from entry to return -- walk start-ups, the
multiplier table of an adding walk, the baby steps of a table, the giant
steps, and the verification of every candidate answer.  What the library does
*not* count: hash-table inserts and lookups, hashing, the canonicalisation of
a point for the negation map, and the arithmetic on exponents.  Those are
neither charged nor reported.

`ecbench.gae` charges one unit per group addition or doubling whatever its
field cost, keeps phases apart (`setup`, `search`, `internal_verification`),
and *counts* the work it does not price -- `inserts_uncharged`,
`canonicalisations_uncharged` -- so that a bound in that unit says `bounded:
true` and shows the unpriced work beside the priced.  The two units draw
their boundaries in different places, in different code, on different
groups: ecbench's curves are its ICV1 registry, this library's are
`find_prime_order_curve` and `find_safe_prime` at a bit length.  A number in
one unit is not a number in the other, and the frontier does not compare
them: a domain is hashed over its unit, so a `cryptanalysis.group_ops` record
and an `ecbench.gae` record can never be on one table.  What *can* be read
across the two pages is the shape of the result -- which methods tie, where
set-up flattens the slope, how wide an interval 16 runs per size leaves.

Consequences carried in every record here:

- `uncharged_per_sqrt_r` is `0.0` and `admissibility.bounded` is `false`.
  This is the sum over the counters the unit declares unpriced, of which this
  library has none; it is what ecbench itself reports for a method without
  `*_uncharged` counters.  It does **not** say that table and hash work is
  free; it says the unit does not see it.  The wall-clock columns of
  `docs/BENCHMARKS.md` are where that cost shows, and wall time never enters
  a record.
- `memory` is `ca_stats.table_entries / sqrt(N)`: the baby-step table (BSGS),
  the three-walk table (grumpy giants), the distinguished-point table (rho)
  or the trap table (kangaroo).  All four solvers report it, so the axis is
  known on every record.
- The floor `sqrt(pi / 2A)` counts negation on a curve and nothing in
  `Z_p^*`.  It is a model of random collision search, not a bound on
  deterministic walks: the documented constant of grumpy giants, `1.18`, sits
  *below* the `Z_p^*` floor `1.253`, and its measured ratio to the floor is
  about 1.0.  Read `ops` as a normalisation, not as a distance from a theorem.
- The negation map is the library's default on curves (`ca_rho_params.negation_map
  = 1`), so the method `ca.rho` carries the same parameters, and the same
  `method_id`, in both group kinds; the domain's family says whether the map
  applied.

## Regenerating

Prerequisites: the library built at the top level (`make lib`, which gives
`build/ca_bench`), Python 3.10+ with pytest, and an `ecbench` binary built
from aburan28/crypto for the frontier (`ECBENCH=/path/to/ecbench`; only the
frontier step needs it).

```sh
cd experiments/bounds
make test                     # the seal round trip and the adapter (pytest)
make sweep                    # build/ca_bench complexity --bits 20,24,28,32,36 --reps 16 --json sweeps/complexity-$(date -u +%Y%m%d).jsonl
make records                  # emit_bounds.py emit on the newest sweep -> records/
make frontier ECBENCH=/abs/path/ecbench   # frontier.json and FRONTIER.md, built from the repository root
make check    ECBENCH=/abs/path/ecbench   # fails when the committed page is stale
make list                     # every record's seal, id and headline
```

`BITS=`, `REPS=` and `SWEEP=` override the defaults.  `ca_bench generic
--json` writes rows of the same shape (with `rho-1` and the multi-threaded
`rho-T`, which the adapter leaves out because the envelope is one thread);
`complexity` also writes `precomp-online` rows, which the adapter leaves out
because precomputation is a different domain, not a better entry in this one.

What a re-run changes: the sweep's seeds are fixed (`ca_bench` seeds the
target generator with `7 + bits` and the walks with `100 + instance`), so a
re-run of the same binary reproduces every operation count; the `seconds`
column, the header's `binary_sha256` and `git_commit`, and therefore the
sweep's hash and every record id, change with every build.  Records are
write-once in ecbench's sense -- a changed byte is a different record -- and
the file names here are labels (`ca-<group>-<method>-<tier>.json`), as
ecbench's are, so `make records` from a new sweep overwrites the files with
new ids and the old ones stay in git history.  The sweep header's
`git_commit` is the commit the build was *configured* at (CMake re-runs when
`HEAD` moves); `binary_sha256` is the exact identity of the producer.  `host`
is `uname(2)`'s sysname, nodename, release, version and machine -- the first
five fields of `uname -a`.

## What the first page says

Sweep of 2026-10-06: `ca_bench complexity --bits 20,24,28,32,36 --reps 16`,
one 4-core container, one thread.  Field sizes 20-32 bits form the `toy`
tier (four sizes, `level: exponent`); 36 bits is alone in `medium` (one size,
`level: constant`, no exponent).  Every run verified; all 16 records are
admissible.  Ids are in `FRONTIER.md` and `make list`.

| method | group | tier | α (95 %) | S = ops/√N (95 %) | ops × floor (95 %) | memory /√N | documented S |
|:--|:--|:--|:--|:--|:--|--:|--:|
| `ca.bsgs` | zp | toy | 0.497 [0.441, 0.547] | 1.468 [1.371, 1.570] | 1.17 [1.09, 1.25] | 1.00 | 1.5 |
| `ca.bsgs` | ec | toy | 0.497 [0.441, 0.547] | 1.468 [1.370, 1.569] | 1.66 [1.54, 1.77] | 1.00 | 1.5 |
| `ca.rho` | zp | toy | 0.448 [0.394, 0.508] | 1.798 [1.492, 2.102] | 1.43 [1.21, 1.69] | 0.07 | 1.253 |
| `ca.rho` | ec | toy | 0.420 [0.335, 0.511] | 1.774 [1.347, 2.154] | 2.00 [1.50, 2.45] | 0.06 | 0.886 |
| `ca.kangaroo` | zp | toy | 0.508 [0.369, 0.612] | 1.853 [1.565, 2.180] | 1.48 [1.26, 1.75] | 0.07 | 2 |
| `ca.kangaroo` | ec | toy | 0.529 [0.398, 0.645] | 1.763 [1.504, 2.048] | 1.99 [1.69, 2.32] | 0.10 | 2 |
| `ca.grumpy` | zp | toy | 0.495 [0.388, 0.599] | 1.272 [1.085, 1.478] | 1.01 [0.87, 1.17] | 1.26 | 1.18 |
| `ca.grumpy` | ec | toy | 0.498 [0.431, 0.563] | 1.218 [1.082, 1.369] | 1.37 [1.23, 1.55] | 1.21 | 1.18 |
| `ca.bsgs` | zp | medium | – | 1.397 [1.252, 1.548] | 1.11 [0.99, 1.24] | 1.00 | 1.5 |
| `ca.bsgs` | ec | medium | – | 1.397 [1.252, 1.548] | 1.58 [1.40, 1.76] | 1.00 | 1.5 |
| `ca.rho` | zp | medium | – | 1.458 [1.008, 1.976] | 1.16 [0.81, 1.55] | 0.01 | 1.253 |
| `ca.rho` | ec | medium | – | 0.944 [0.708, 1.191] | 1.07 [0.80, 1.34] | 0.05 | 0.886 |
| `ca.kangaroo` | zp | medium | – | 2.007 [1.703, 2.306] | 1.60 [1.37, 1.82] | 0.00 | 2 |
| `ca.kangaroo` | ec | medium | – | 2.058 [1.606, 2.502] | 2.32 [1.79, 2.82] | 0.03 | 2 |
| `ca.grumpy` | zp | medium | – | 1.290 [1.053, 1.556] | 1.03 [0.84, 1.23] | 1.29 | 1.18 |
| `ca.grumpy` | ec | medium | – | 1.053 [0.833, 1.279] | 1.19 [0.94, 1.43] | 1.05 | 1.18 |

(Each row is the record's `fit.alpha`, `constant.s`, `dimensions.ops` and
`dimensions.memory`, rounded; the per-size rows are in the records.  The
`medium` memory figures `0.00` and `0.01` are `0.004` and `0.006`.)

Read honestly:

- **Every fitted exponent's interval contains 1/2**, and every point estimate
  is within 0.08 of it.  That is the same as `docs/BENCHMARKS.md`'s complexity
  table (5 sizes, 5 instances: `0.487`, `0.477`, `0.526`, `0.502` in `Z_p^*`;
  `0.487`, `0.428`, `0.494`, `0.480` on curves) and says what that table says:
  the four methods are square-root methods on these groups.  It is a scaling
  claim over 2^18 - 2^31 and nothing more.
- **BSGS** measures `S = 1.47` against the documented `1.5` (BENCHMARKS:
  `1.508`), identically in both group kinds, as it must: its cost is a
  function of the target and the order alone.  On a curve it is `1.66 ×` the
  floor, because the floor credits negation and the library's BSGS does not
  use it.
- **Rho** is the record to read with care.  The documented constants are the
  random-walk figures `sqrt(pi/2) = 1.253` and, with the negation map,
  `sqrt(pi/4) = 0.886`.  The toy records measure `1.80` and `1.77`: `1.4 ×`
  and `2.0 ×` the respective floors.  The per-size rows show why: `S` falls
  from `2.18` (20 bits) to `1.48` (32 bits) in `Z_p^*` and from `2.13` to
  `1.17` on curves, and at 36 bits it is `1.46` and `0.94` -- within 7 % of
  the declared value on curves, with an interval `[0.71, 1.19]` that contains
  it.  The library charges the adding walk's set-up (its multiplier table and
  each walk's start, about `3 log2 n` operations) to `group_ops`, and at
  `2^20` that is a large share of a `sqrt(n)` search.  So the fitted `α`
  (`0.448`, `0.420`) sits below 1/2 and the toy constant above the law, for
  the reason ecbench's `docs/bounds/README.md` §4 names: "fixed costs pull α
  below the law at small sizes".  BENCHMARKS reports the same (`0.477` /
  `1.781`, `0.428` / `1.572`).  This library has no phase counters, so there is
  no `setup` stage row to confirm the share directly; the trend across sizes
  is the evidence.
- **Kangaroo** measures `1.85` / `1.76` toy and `2.01` / `2.06` at 36 bits
  against the textbook `2`; its memory is a few thousand traps (`0.00 - 0.10
  sqrt(N)`).  Its `α` intervals are the widest (`[0.37, 0.61]`,
  `[0.40, 0.65]`): the herd's cost has the spread of a random walk and 16
  runs per size do not pin it.
- **Grumpy giants** measure `1.27` / `1.22` toy and `1.29` / `1.05` at 36
  bits against the `1.18` of the 400-instance simulation in
  `docs/ALGORITHMS.md`; every interval contains it.  It leads the `ops`
  column in three of the four domains (in `ec_prime` medium rho's `1.07` is
  ahead of its `1.19`), at the price of a `1.05 - 1.29 sqrt(N)` table.
- **The frontier** keeps all four methods in both toy tiers and in `zp`
  medium: the table methods lead on `ops`, the walks on `memory`, no entry is
  clearly better on both, and ties stand.  In `ec_prime` medium, rho's
  interval on `ops` lies below BSGS's and its memory below everyone's, so it
  dominates BSGS on both axes and grumpy giants on memory -- on one size with
  16 runs, which the page shows beside the result.
- **The intervals are wide.**  Four sizes with 16 instances each give `α`
  intervals of `± 0.05` (BSGS) to `± 0.12` (kangaroo) and constant intervals
  of `± 7 %` (BSGS) to `± 23 %` (rho on curves); the single-size 36-bit
  constants are wider still (`± 11 %` to `± 33 %`).  In the toy tiers nothing
  separates rho from kangaroo on `ops`; only the 36-bit curve record does,
  and that is one size.  More instances tighten the constants; more sizes
  above 32 bits would give the medium tier an exponent.

## What is not claimed

- Nothing about `ecbench.gae`, ecbench's methods, or how this library
  compares with that harness.  The units differ and no domain mixes them.
- Nothing about sizes other than those measured: toy stays toy, and the
  36-bit records are constants at one size with no exponent.  Nothing about
  cryptographic sizes.
- No lower bound and no theorem.  `ops` is a ratio to a model of collision
  search; the documented constants are the library's own documentation
  (`README.md`, `docs/ALGORITHMS.md`), not derivations checked here.
- **The intervals are this adapter's.**  They come from a Python port of
  ecbench's two-stage bootstrap (sizes resampled, then runs within; 2000
  resamples; seed 20261005; the same `splitmix64` resampler) that has not
  been verified against ecbench on shared data.  They are not bit-comparable
  with the intervals in ecbench's records, and a reader should treat them as
  a statement of this code, re-derivable from the committed sweep by `make
  records`.
- `ecbench bound check` -- re-derivation from a named ecbench session with
  its plan, records and audit receipts -- **does not apply** to these records:
  their session is a `ca_bench` sweep.  Re-derivation here is `make records`
  on the committed sweep, which reproduces the same bytes and ids.
- No isolation level was measured (`levels: {"L0": runs}`) and no wall time
  enters any record; the `seconds` column of the sweep is a practicality note
  for the reader of `docs/BENCHMARKS.md`, nothing more.  No audit receipt
  exists (`audits: []`).
- `deterministic: true` means: fixed seeds, one thread, and two sweeps from
  builds of the same sources (before and after the commit, so two binaries)
  reproduced every `group_ops`, `iterations` and `table_entries` value of
  each other, all 800 rows (checked before the records were committed), and
  `make records` on the committed sweep writes the same bytes.  It is not a
  statement about multi-threaded runs, which the adapter leaves out.
- `bounded: false` and `uncharged: 0.0` are statements about the unit's
  boundary, not about the cost of the work outside it.

## Files

```text
experiments/bounds/
  README.md           this note
  emit_bounds.py      the adapter: sweep -> records (emit), seal and id check (list)
  test_seal.py        the seal proved on real ecbench records; the adapter on a synthetic sweep
  testdata/           two ecbench records, byte for byte (aburan28/crypto docs/bounds/records at 85be1540)
  Makefile            sweep, records, frontier, check, test, list
  sweeps/*.jsonl      ca_bench --json output: a header line, then one row per solved instance
  records/*.json      ecbench.bound/v1 records, named by label, identified by bound_id
  frontier.json       built by ecbench frontier build; do not edit
  FRONTIER.md         the same, as a page; do not edit
```
