# Frozen five-summand point solver trial

The source and public uniform subgroup target streams were frozen in `manifest.json`
before the archived run. The native algorithm builds a table of every unordered
pair sum from a signed subgroup point set. For each target it scans unordered
triples and looks up the residual pair, replaying every match with the group
law. A paired three-summand direct search uses the *same* table, base, targets
and resource limits. Both methods run on ordinary targets; one separately
labelled planted target per field is a correctness check excluded from yield.

The n=13 case uses all 26 archived signed points and 24 frozen targets. The
n=83 case uses the first 64 canonical representatives and both signs (128
points), with four frozen targets. The complete n=83 base has 130,604 signed
points, requiring 8,528,767,710 unordered pair entries; this solver explicitly
rejects more than 1,500,000 entries under a 512 MiB process limit. Even eight
bytes of index payload per pair would exceed 68 GB. Thus **n=83 subset results
are not measurements of full-base natural relation yield**. An exhausted
subset search proves only the absence of a witness among its points; a budget
status proves neither absence nor presence.

Each ordinary target is generated independently from a uniform nonzero scalar
in the certified subgroup. The native process only receives the public points.
The audit independently regenerates each target, checks each witness using the
Python curve library, and updates rank modulo the subgroup prime. Receipts
include every failed attempt, full-base construction, workload generation,
archive loading, subprocess wall time, audit time, and native peak RSS.
`charged_wall_seconds` includes the latter costs for the five-summand arm;
it excludes the separate planted control and paired three-summand process.
For a valid paired comparison add the same shared costs and a separate audit
allocation to the baseline. The n=13 pilot is one target stream, not the
five-seed/rank-eight gate for a 2× improvement.

The per-target budget is 50,000 triple checks or five seconds. Compiler setup
and fixture archival are outside the charged time. The native arithmetic is
the already frozen field/curve code from `explicit_base_frontier.cpp`; its
source hash is bound into this manifest. Every projected point was checked
against the full base archive. This remains a PDP-stage diagnostic; no
relation matrix, target descent or discrete logarithm is solved.

```sh
python -m unittest discover -s experiments/pdp-scaling -p test_five_sum_mitm.py -v
python experiments/pdp-scaling/five_sum_campaign.py run experiments/pdp-scaling/five-sum-20260928/manifest.json /tmp/five-sum-replay
```
