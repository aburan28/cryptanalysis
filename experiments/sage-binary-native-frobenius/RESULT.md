# Native Koblitz Frobenius: PASS_LOCAL

The installed local Sage 10.10.rc0 fork now applies positive Koblitz Frobenius
powers through NTL `GF2E` squaring and constructs ordinary Sage finite-field
points through the already validated direct initialization path. The public
`frobenius_points` API still validates the curve and each point, reduces powers
modulo the field degree, preserves identity results for infinity and zero
power, and uses the previous Python path for non-NTL fields. Custom point
classes retain their constructor hooks. An input iterator is fully consumed
before restoring NTL's field context.

## Complete verified API timing

The incumbent is the frozen Python module in `baseline/`; its Frobenius code
does not call the installed native extension. Each cell measures twelve
balanced paired rounds. Every timed call constructs all output Sage points and
compares them exactly with an independently constructed Sage Frobenius isogeny
result. The 1,105,920 verified timed output points agree. Fixture generation
and isogeny construction occur outside the timed call. Speedups use the median
of paired log ratios within each cell, then the geometric mean across cells.

| Suite | Field degree | Points | Power | Incumbent median ms | Native median ms | Paired speedup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Primary | 19 | 64 | 1 | 0.100 | 0.052 | 1.896x |
| Primary | 67 | 1,024 | 1 | 1.579 | 0.824 | 1.916x |
| Primary | 131 | 4,096 | 1 | 8.804 | 3.534 | 2.372x |
| Primary | 131 | 1,024 | 7 | 4.439 | 1.414 | 2.470x |
| Confirmation | 31 | 256 | 1 | 0.413 | 0.212 | 1.948x |
| Confirmation | 163 | 2,304 | 1 | 8.414 | 3.240 | 2.333x |
| Confirmation | 163 | 256 | 11 | 1.006 | 0.321 | 2.729x |

Primary geometric mean: **2.148x**, paired-round bootstrap 95% interval
**1.946–2.397x**. Independent confirmation geometric mean: **2.315x**,
interval **2.017–3.128x**. Bootstrap resamples each cell's twelve paired log
ratios independently, 10,000 times. These intervals describe this local run;
they are not estimates of performance across different hosts. The measurements
are complete point-map calls, not scalar point addition, scalar multiplication,
or a full ECDLP workload. No earlier speedup is multiplied into this result.

## Correctness and resources

- The existing 19 arithmetic and point-construction test groups pass. The three
  new native Frobenius groups pass, covering powers 1, 2, 7, -1, degree and
  degree+1; fields through degree 163; point state and interoperability; an
  iterator that switches NTL's modulus; custom point classes; and the Python
  fallback. The six hardware-backend regression groups and all 15 API doctests
  also pass.
- Fresh-process peak RSS for twelve verified 4,096-point calls at degree 131
  is 263,258,112 bytes for the incumbent and 263,241,728 bytes for the native
  path. The difference is within process-level noise. The native path retains
  an O(n) list of validated point triples before restoring NTL's context.
- A separate eight-round diagnostic at degree 131 with 256 points gives
  5.589x at power 65 and 5.131x at power 130. It checks the high-power path
  but is not included in either frozen acceptance suite.
- `native-frobenius.patch` is the exact incremental source diff from the frozen
  incumbent. `install-001/` records the local extension build and installation.
  The raw paired rounds, per-cell output counts and binary hashes are in
  `primary-001/` and `confirmation-001/`. `report.py` recomputes the suite
  estimates and intervals from those rounds.

The earlier vector-storage candidate is separately recorded as a hold in
`../sage-binary-storage/RESULT.md`; its source and installed binary were
restored before this experiment.
