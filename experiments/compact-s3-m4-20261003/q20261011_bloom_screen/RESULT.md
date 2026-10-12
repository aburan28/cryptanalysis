# Q1446: dense Bloom removes 8 million replay pair sums at N83

A 40-bit-per-key, 20-hash Bloom filter produced zero false positives on
Q1445's frozen 8-million-table, 65,536-query-representative ordinary N83
cell. The original 20-bit, 10-hash filter produced 1,180 false positives and
therefore replayed all 8 million table pairs. Q1446 performed **8,065,536**
charged group pair sums (table plus query) versus **16,065,536** for Q1445,
a **49.8% reduction in that operation class**. Both performed 10,878,976
target signed-x complements. The Bloom allocation grew from 20,065,536 to
40,065,536 bytes; observed peak RSS grew from 1,261,600,768 to
1,281,540,096 bytes. The native table/query/exact-replay phases were
23.41 / 18.15 / approximately 0 seconds, with 45.07 seconds process wall.
These wall observations are exploratory because the host was not isolated.

The comparison changes only Bloom density. It uses the same executable,
ordinary public target, exact Q1325 base, pair schedule, 8-million descriptor
table, 65,536 representatives, worker count, and 180-second cap. The field
is GF(2^83), curve `EC1N83Ckb1h876c2921cb64`, workload
`bab50a1e5f66`, B=30,977,592, K=186,612, base SHA-256
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`,
and `isogeny: "none"`. `Q1446` is a PDP-stage proposal;
`candidate_id` and `run_id` are null. The source, binary, base, Q1445
receipt, and exact settings were frozen in [freeze.json](freeze.json).

A one-descriptor positive control using Q1401's public point returned the
same exact hit key `145376b70583ec992f77` at table/query positions zero.
Q1401's archived independent full-point replay verifies the four leaves and
their sum; [control.json](control.json) binds the parent replay and this
native control. [validate.py](validate.py) passes identity, raw-output,
operation-count, memory, and positive-control checks. The ordinary cell
finished with `no_exact_hit_at_cap`; its charge is preserved in
[measurement.json](measurement.json).

Across Q1400, Q1445, and Q1446 on this same ordinary point, the quotient-pair
lane has charged 32,000,000 table pair sums including all exact replays,
212,992 query pair sums, and 35,356,672 target signed-x complements. These
are distinct operation classes; they are not added into a field-operation
estimate or compared directly to the SAT lane's API entries.

Q1446 removes replay overhead but does not change the pair-match probability
or Q1416's N131 pure-index work model. The latter remains `2^89.36`
logical pair actions, 28.36 bits above the abstract `2^61` action cap under
its stated assumptions. A fully charged N131 IC solve exponent and numerical
challenge gap remain unmeasured. The next algorithmic gate is to change how
candidate pair sums are found, rather than extend this low-density N83 table.
