# Active-suffix GPU pivot panels

This opt-in GF(2) matrix experiment improves the round7 Metal RREF kernel.
The separate final-source physical M4 Pro confirmation finds **1.38–1.40×**
paired wall-time gains on the two captured 2915-by-4096 matrices. It does
**not** establish a CPU/GPU crossover: the new GPU takes 14.29–14.37 ms while
M4RI takes 12.38–12.54 ms. CPU solver dispatch is unchanged.

The scope is internal matrix reduction. Complete polynomial construction,
basis completion, independent algebraic certificates and curve replay are
absent from this interval. This is not a complete query, final IC relation
linear algebra, F5 signature-safe reduction or an F6 novelty claim. The
one-unseen-target IC/rho acceptance gate remains a separate requirement.

## Algorithm and invariants

At panel entry, rank `r` and column `c` delimit the active suffix. Every active
row is zero before `c`. The kernel caches only rows `[r,rows)` of one column
word and the forward-elimination masks, plus the trailing words of the panel
rows. It selects a 16- or 32-pivot capacity from the actual remaining scratch
memory, accounting for the pipeline's static memory. The host uses the frozen
global-memory pivot kernel when the initial 16-pivot allocation does not fit.

Panel rows remain in forward echelon form while pivots are selected. Earlier
panel rows never change during this phase. Each active-row mask records the
coefficients that eliminate that row against those forward rows. Its next bit
is the raw column bit XOR the parity of its current mask intersected with the
panel column. Swaps preserve both the column cache and masks.

At panel completion, the pivot submatrix is unit upper triangular. The kernel
inverts it using bit-mask substitution and writes each RREF panel row once as
a combination of the immutable forward rows. Each untouched row's raw bits at
the final pivot columns are now exactly its coefficients against that RREF
panel. This includes **earlier pivot rows**; eliminating them preserves full
canonical RREF rather than merely producing forward echelon form. Table
construction splits the panel into independent eight-bit Four-Russians tables.
No numerical pivots, coefficients, roots or answers are reused across inputs.

Table/update kernels map work onto the trailing words. An optional indirect
dispatch computes the number of remaining threadgroups on the GPU, following
Apple's [indirect dispatch layout and ordering API](https://developer.apple.com/documentation/metal/mtlcomputecommandencoder/dispatchthreadgroups(indirectbuffer:indirectbufferoffset:threadsperthreadgroup:)).
It applies only to one local-panel matrix; batches and global-panel fallbacks
retain direct dispatch. The `--direct` control keeps fixed dispatch sizes.
Neither route reads back pivots between panels. Finished matrices have zero
update work. Exact tests cover both finished and unequal-rank batch members.

## Final-source physical confirmation

Apple M4 Pro, 14 logical CPUs, macOS ARM64. Each of six frozen inputs has one
warmup and 31 measured repetitions with shuffled CPU/previous-GPU/active16/
active32 order. The CPU is M4RI `k=5` at `USER_INITIATED` QoS. The measured
candidate below uses **512 pivot threads, a maximum of 16 pivots, and direct
dispatch**. All initial/group/final one-minute load checks admit. Inputs and
pipeline construction are outside timing; allocations, transfers, dispatch,
synchronization, extraction and Metal buffer destruction are inside. Exact
rank/RREF comparison is outside timing and mandatory for every sample.

| Matrix | CPU ms | Previous GPU ms | Active16 GPU ms | Previous / active16 [95%] |
| --- | ---: | ---: | ---: | --- |
| Captured seed1 | 12.5425 | 20.3680 | 14.2903 | 1.404 [1.388, 1.418] |
| Captured seed2 | 12.3797 | 20.0689 | 14.3651 | 1.384 [1.368, 1.399] |
| Random 256 × 1024 | 0.0600 | 1.1751 | 0.8635 | 1.382 [1.336, 1.440] |
| Random 1536 × 3072 | 2.2081 | 8.1547 | 5.8428 | 1.398 [1.361, 1.436] |
| Random 2048 × 4096 | 4.5983 | 12.1523 | 8.5225 | 1.414 [1.382, 1.448] |
| Captured seed1 with duplicate rows | 5.8175 | 15.4289 | 11.9106 | 1.296 [1.276, 1.316] |

Times are medians; ratios are paired geometric means with individual,
unadjusted 95% bootstrap intervals. The CPU/active16 capture ratios are
0.867 [0.858,0.876] and 0.851 [0.841,0.861]. CPU wins every control. These
intervals describe repeated calls on this host, not independent targets.
The wider candidate and all raw samples remain in `results/measure.json.gz`.

## Exploratory results and limitations

The initial active-suffix design still reduced previous panel rows at each
pivot. It passed 3,168 exact checks, but adaptive 32-pivot panels regressed to
about 24 ms against a 20 ms GPU baseline. Deferring panel reduction improved
the 256-thread, 16-pivot variant to about 18 ms. Reducing the pivot group to
64 threads was strongly negative on the captures (about 38 ms). The 512-thread
version reached about 14.4 ms. A 1,024-thread screen reached about 14.1 ms;
that small difference is not a matched 512-versus-1024 superiority claim.
Indirect dispatch passed exact checks but did not give a clear capture win.
The successful final confirmation therefore uses the 512-thread direct route.

An initial shader compilation error and two initial-load timing rejections
are retained in the external evidence archive. None is counted as a timing
win. Exploratory screens selected the final candidate; they are distinct from
the final-source confirmation above. `results/exploration.json` indexes these
outcomes and their source/report hashes. The full source snapshots, binaries,
logs and receipts remain in the task's `active-panel` evidence archive.

The experiment checks actual Metal pipeline thread and memory limits. A
requested unsupported pipeline fails explicitly. The portable CPU path in
the solver remains available and default. Physical M4 Pro execution does not
establish performance on another Apple GPU, NVIDIA, AMD or Intel hardware.
CI rebuilds native M4RI/host code and executes Metal correctness controls;
any hosted device identity is recorded and must not be described as physical
hardware. Correctness is not a performance qualification.

## Reproduction and validation

Use Python 3.11+ and a local Metal-capable Mac with M4RI. Choose a fresh output
directory; the runner never overwrites a prior outcome.

```sh
python experiments/groebner-perf-20260924/round29/run.py \
  --output /absolute/path/new-confirmation --m4ri-prefix /path/to/m4ri \
  --threads 512 --direct
python experiments/groebner-perf-20260924/round29/audit.py \
  /absolute/path/new-confirmation
python experiments/groebner-perf-20260924/round29/test_audit.py \
  --bundle /absolute/path/new-confirmation
```

Omit `--direct` to test indirect dispatch; use `--mode correctness` for a
correctness-only run. `--threads` is explicit; its conservative default is
256, not a device-specific automatic performance choice.

Each native correctness run checks **3,168 exact rank/RREF outputs** against
M4RI. Controls include exhaustive tiny matrices; word/panel boundaries; zero,
duplicate and gapped rows; 4,097/8,192-row global fallbacks; both panel widths;
forced memory fallback; distinct batch ranks; and invalid shape/padding input.
The final confirmation adds **576 exact comparisons**. Sixteen Python test
groups validate retained records and reject missing pairs, matrix/rank/arm
substitutions, wrong warmups, overloaded groups, invalid/omitted wall time,
missing panel work, changed binaries/libraries and self-consistent untrusted
sources. Full receipts bind all six experiment sources to their current
trusted files, source snapshots, compiler flags, native binary, loaded M4RI,
frozen input and raw reports. Repository results are compact receipts; the
full binary bundle is rebuilt in CI and archived externally.

The next GPU gate remains an admitted advantage over the strongest CPU
baseline, followed by complete-query integration and independent verification.
