# The distributed protocol

`ca_rho_solve` is one process that walks, stores its own distinguished points
and finds its own collision. That does not distribute. Running it on N
machines with N seeds is N independent searches: each expects the full
`1.25·√n` steps, the fleet's *chance* of an early answer improves, and its
total work is N times one machine's.

The parallel collision search of van Oorschot and Wiener distributes because
every walker iterates **the same function** and reports only its
distinguished points. Two walks that ever meet stay together and arrive at
the same distinguished point, whichever machines they ran on, so P machines
finish in expected `1/P` of the time for the same total work.
[`ca_dist.h`](../include/cryptanalysis/ca_dist.h) is that protocol, split into
the two halves a fleet needs, and [`orchestrator/`](../orchestrator/README.md)
is the service layer that schedules it.

```
        agent                             server
  ca_dist_walk(campaign, unit)  ─points─▶  ca_dist_merger_add
        (no state, no answer)              (verify, store, solve)
```

## The walk

An r-adding walk, identical in shape to `rho.c`'s. Multipliers
`M_i = α_i·G + β_i·H` for `i < r`; state `(Y, a, b)` with `Y = a·G + b·H`; one
step is

```
i = (hash(Y) >> 32) mod r ;  Y ← Y + M_i ;  (a, b) ← (a + α_i, b + β_i)
```

and `Y` is *distinguished* when the low `dp_bits` of `hash(Y)` are zero. A
distinguished point goes on the wire as 32 fixed little-endian bytes:

```
  w0 (8)      canonical first word   — x on a curve, the residue in Z_p^*
  w1 (8)      canonical second word  — y on a curve, zero in Z_p^*
  a  (8)      exponent of the base,   reduced mod n
  b  (8)      exponent of the target, reduced mod n
```

No framing, no header: a corpus is a concatenation of records, so a truncated
upload is a *shorter* upload rather than a corrupt one, and two corpora merge
with `cat`.

## Three properties the fleet is built on

**One walk function, fleet-wide.** The multipliers come from the campaign
seed alone — nothing about the unit, the agent or the machine enters them.
`ca_dist_campaign_id` hashes the group, the base, the target, the seed, `r`
and `dp_bits`; agents that disagree on any of it are running different
searches whose points can never collide, which is a failure that otherwise
produces no error at all, just a fleet that never finds anything.

**Units are deterministic, therefore replayable.** A unit's starting points
come from `(campaign seed, unit id, walk index)`, and a walk that is abandoned
restarts from the *next deterministic start* rather than from a PRNG. Run a
unit twice and you get byte-identical points. That is what makes at-least-once
delivery safe: a scheduler that cannot tell whether an agent died just
re-issues the unit, and the duplicate points cost bandwidth and nothing else.

**The merger trusts nothing.** Every submitted point is checked — the
coordinates must be a group element, the point must really be distinguished
under this campaign's cutoff, and `Y = a·G + b·H` must really hold. That is
two scalar multiplications against the `2^dp_bits` walk steps that produced
the point, so it is affordable at the server even when no agent is trusted.
A collision then yields a *candidate* `x` from `(b₁ − b₂)·x ≡ a₂ − a₁ (mod n)`,
and the candidate is verified against `x·G == H` before it is reported. A
buggy walker, a hostile agent or a 64-bit hash collision costs a rejected
point, never a wrong answer.

## Using it from the command line

```sh
# One agent's unit: a budget of walk steps, points to a file.
ca dist-walk --group zp --p 2000000579 --order 1000000289 --g <G> --h <H> \
             --campaign-seed 12345 --dp-bits 6 --unit 3 --steps 20000 \
             --out unit-3.bin
{"status":"ok","campaign":3904165131322950742,"unit":3,"points":333,...}

# The server's side, over any number of units from any number of machines.
ca dist-merge --group zp --p 2000000579 --order 1000000289 --g <G> --h <H> \
              --campaign-seed 12345 --dp-bits 6 unit-*.bin
{"status":"ok","accepted":2513,"duplicates":0,"rejected":0,"stored":2449,
 "solved":true,"x":821034685}
```

`dist-merge` exits 0 whether or not it solved: "no collision yet" is the
normal state of a campaign, and a scheduler that read it as failure would
retry the whole corpus every pass. `--campaign-seed` is required rather than
defaulted, because a walker that invents its own seed produces points that
merge with nobody — silently.

## Choosing `dp_bits`

`dp_bits` trades corpus size against the tail. Points arrive one per `2^dp`
steps, so a full search produces about `1.25·√n / 2^dp` of them; the library's
auto-resolution aims for about a million, which keeps the corpus in tens of
megabytes and amortises a network round trip over `2^dp` steps of walking.

The cost of raising it is the *tail*: every walk in flight when the collision
lands is wasted, and walks are `2^dp` steps long on average. That is
negligible at a handful of machines and is the dominant term at thousands. If
a campaign is going to run on a large fleet, lower the cutoff **before it
starts** — `dp_bits` is part of the campaign's identity, so changing it
mid-campaign starts a second search that cannot merge with the first.

## What is deliberately not in the protocol

**The negation map.** `ca_rho_solve` uses it for its `√2` on curves. The
distributed walk does not: the fruitless cycles it causes have to be escaped
with per-walk state (a look-ahead rule and a sliding window) whose behaviour
must agree bit for bit on every machine, and a distributed walk that disagrees
with itself does not fail loudly — it quietly stops finding collisions. The
`√2` is not worth that failure mode; a campaign that wants it should get it
from a single-process solver on one large machine.

**Identity points.** `Y = 0` is a relation that would solve the instance
outright, and it is also the one point whose coordinates carry nothing: the
32-byte record has no way to say "infinity", and a walk cannot continue from
it. It happens with probability about `1/n` per step — never, at these sizes
— so the walker drops it and restarts rather than the format growing a case
for it.

**Any performance claim.** This is a protocol, not an optimisation: the
per-step cost is `rho.c`'s, measured in [BENCHMARKS.md](BENCHMARKS.md). What
it changes is the *shape* of the search — from N independent searches to one
search on N machines — and that is a statement about the algorithm, not a
measurement of this code.
