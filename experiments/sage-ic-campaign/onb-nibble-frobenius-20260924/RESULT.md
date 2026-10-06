# Result: delay hot ONB Frobenius table construction

The accepted field source is SHA-256
`dded18a11f243fa269277bfe3513f12a83e9eb28300becf08c9f3d6b5634a07e`
in both the local and IC runner copies. The parent is
`7e9c9e14fcd215ec75414a43e28472fc206721be451f0a2e5c47b99c0676613c`.
For degree 131, each hot exponent uses the original bit loop for calls 1-35
and builds the existing byte table on call 36. Degree 5 and 9 keep their
previous route. At most two byte tables and two small counters exist per
field object.

| Warm operation, candidate speed / parent speed | Run A | Run B |
| --- | ---: | ---: |
| Degree 5 Frobenius, exponent 1 / 2 | 1.000× / 0.999× | 0.990× / 1.110× |
| Degree 9 Frobenius, exponent 1 / 2 | 1.002× / 0.999× | 1.001× / 1.005× |
| Degree 131 Frobenius, exponent 1 / 2 | 1.063× / 0.962× | 1.013× / 0.977× |
| Degree 131 runner-style `pointFromX` | 1.008× | 0.958× |

The paired benchmark used identical seeded inputs, nine alternating matched
rounds, and exact output checks before and during timing. Degree-131 inputs
exceed the 36-call threshold before steady timing. The runner-style point
benchmark uses the runner's Euclid inverse and parity trace on both sides,
without audit-counter overhead.

| Fresh-process `pointFromX` median | Parent A | Candidate A | Parent B | Candidate B |
| --- | ---: | ---: | ---: | ---: |
| Valid abscissa | 2.753 ms | 1.610 ms | 2.278 ms | 1.515 ms |
| Invalid abscissa | 0.675 ms | 0.151 ms | 0.676 ms | 0.072 ms |

Each cold set used seven alternating fresh processes per side and outcome.
The candidate constructs only the exponent-2 table on the first **valid**
point recovery and no table on the first **invalid** one. Later calls still
pay byte-table construction once an exponent reaches 36 uses. The two cold
sets show meaningful timing variation, so use their range when reasoning
about setup cost. The byte-table memory ceiling is unchanged once both
tables are built.

The held 4-7 bit table layouts built fewer entries but failed the frozen
requirement to retain at least 0.80× parent warm Frobenius speed on both hot
exponents. The accepted rule retains the parent byte-table warm path.

The prior exact suites matched **53,368** Frobenius outputs, **4,639** trace
and point outputs, and **4,152** runner field/curve/`NormalView` outputs.
The 14 Python 3.9 artifact replay tests and three real Python 3.13
solver-independent runner IC tests passed. All seven inherited archive
verifiers passed locally after updating their source checks for this exact
descendant. The SAT-backed full runner is unavailable locally, so complete
verified IC/DLP speedup and calibrated operation-unit totals are **unknown**.
This Python ONB work ran on the Apple Silicon CPU, not Metal.
