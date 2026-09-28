# ECC2K17 five-path first pass (bounded solver-stage diagnostic)

Frozen code commit before measurements: `d9fc6a614093f2123b339f53ad9cdf189c9aa5a6`.
Frozen fixture: `../ecc2k17_five_way.json` (generation command in `freeze_pdp.py`).
The complete raw requests, stdout, stderr, chronological journal, host/source
digests, instance hashes, per-backend summaries and manifest are retained in
`ecc2k17-five-way-first-pass/`. This is an append-only first pass; repeat runs
go to a new directory.

Three seeds of planted ECC2K17 S4 point decomposition, nine Boolean variables,
ordered `[3,3,3]` blocks. Native XOR uses `pycryptosat==5.16.0`. The upstream
M5GB bridge used `manschga/M5GB` commit
`2d063f748e8a16ac5a1d74641c79725df29f67ac`; the local binary digest,
platform and precise solver source hashes are in the receipt. One thread and
five seconds per solve request. The independent group verifier regenerates
each original system and checks actual point sums after Boolean evaluation.

| Backend | Charged total seconds | Complete Boolean bases | Algebraic witnesses | Curve witnesses | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| CryptoMiniSat, native XOR | 0.406 | 0 | 3 | 3 | 3 checked assignments |
| Python XOR propagation control | 0.430 | 0 | 3 | 3 | 3 checked assignments |
| Existing repository F5B | 6.915 | 3 | 0 | 3 | 3 checked bases |
| Block-aware batch F4 prototype | 15.031 | 0 | 0 | 0 | 3 five-second timeouts |
| ElimLin → global batch F4 | 15.032 | 0 | 0 | 0 | 3 five-second timeouts |
| Three-bit guess → block F4 | 15.023 | 0 | 0 | 0 | 3 five-second timeouts |
| Pinned original M5GB C++ | 1.230 | 0 | 0 | 0 | 3 signal-11 exits under initial bridge table cap |

For a timed-out solver the outcome is **unknown**, not mathematical UNSAT.
Backend-reported progress captured before termination: block F4 reached
degree 8 and a matrix of at most 94 rows / 417 columns (separate maxima),
ElimLin→F4 reached degree 6 and 49 rows / 380 columns. The first-pass hybrid
wrapper did not forward branch matrix telemetry. M5GB produced a valid basis on
one small toy control but also an invalid basis and a crash on other controls;
none of its ECC outputs passed certification. A subsequent sanitizer run
located an out-of-range term-table access in the **bridge's bounded table**.
The initial crashes are not evidence that the full M5GB algorithm fails.

Totals begin at backend launch and include failures, repeated requests,
worker lifetime and independent checks. Input generation/encoding, initial
upstream clone/build, environment provisioning and downstream IC/DLP work are
excluded and named in the receipts. The three planted systems estimate neither
ordinary relation yield nor rank of novel independent relations. No 2×
cost-per-independent-relation or end-to-end speedup is established.

## Second frozen pass: hybrid + native XOR

Code and eight-backend manifest were committed at
`cca57445703be865ed7c38bb6ada5c597e9d7418` before the second run.
The new immutable receipts are in `ecc2k17-eight-backend-control/`, with
the same three planted equations, order, watchdog, and single thread.
The native XOR solver again returned 3/3 curve-verified witnesses in **0.401 s**
total. Hybrid guess + native XOR returned 3/3 curve-verified witnesses in
**0.520 s**, after respectively 4, 2 and 2 branches on the three seeds.
Its branches with no witnesses are charged and are not certified UNSAT.
Existing F5B certified 3/3 complete bases in **6.645 s**. All 3 attempts
each for block F4 (**15.026 s**), ElimLin→F4 (**15.024 s**), and hybrid→F4
(**15.024 s**) timed out. M5GB again exited on signal 11 for all 3 seeds
(**1.266 s**) under that same bridge cap. Hybrid F4 reached degree 6 and backend-reported matrix maxima
of 350 rows and 64 columns before termination; other maxima appear in the
first pass above. This is a **negative** result for specialization + SAT on
these three planted inputs, with no claim of statistical significance.

## Corrected M5GB table-bound control

After the sanitizer located out-of-range term-table indexing in the earlier
bridge, the bridge and third frozen manifest were committed at
`fa16e1348b19b513fccc0bfc8f3210c7b405395d` **before** this control.
The unmodified pinned M5GB source was rebuilt with checked C++ vector
indexing and table parameter `d=15`. The three original ECC inputs, group
verifier, and five-second request watchdog were reused. The complete third
receipt is in `ecc2k17-m5gb-checked-table/`: total charged **12.035 s**;
three attempts returned **unknown** because the bounded term table was
exceeded (individual requests 4.097, 4.000 and 3.935 seconds). There was
no complete certified basis. The corrected interpretation is a **bridge
resource limit** on this encoding. No conclusion about a properly provisioned
M5GB implementation's speed or feasibility follows from these outcomes.
