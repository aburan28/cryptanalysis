---
name: sheriff
description: "Wildly deep integrity audit of research results in this repository and its siblings: execution proofs and STARK/zk verifiers, Lean theorems (holes, axioms, statement fidelity), solve certificates, cost accounting against matched rho, statistics and preregistration, provenance and replays, and every number in papers. Use for /sheriff, 'is this result real', before a claim, paper or benchmark row lands, after a claimed breakthrough, or on a schedule. Pointer to the canonical skill in aburan28/crypto-autoresearcher; never repairs or changes research state."
---

# Sheriff (pointer)

The canonical skill, its checklist and its tool live in
`aburan28/crypto-autoresearcher`:

- procedure: `.claude/skills/sheriff/SKILL.md`
- beat-by-beat checklist: `docs/sheriff.md`
- deterministic half: `tools/sheriff.py` (`sweep`, `canary`, `check-case`)

Read the canonical `SKILL.md` and follow it. This pointer adds no rule and
lowers none; where it and the canonical skill disagree, the canonical skill
wins. This repository's own `AGENTS.md` evidence rules still bind every
verdict.

## Getting the canonical skill

Use a sibling checkout at `../crypto-autoresearcher`, fetched to `origin/main`.
If there is none, clone it beside this repository, or add it to the session.
Never copy the tool into this repository: two copies of an instrument drift
apart.

## Auditing something in this repository

Run the sweep from the autoresearcher checkout, naming this repository as a
prefix. Its siblings are discovered as `../crypto` and `../cryptanalysis`, or
are passed with `--repo NAME=PATH`.

```sh
cd ../crypto-autoresearcher
python3 tools/sheriff.py sweep --target cryptanalysis:<path> [--deep]   # e.g. cryptanalysis:experiments/koblitz-n83-stacked-20261016
python3 tools/sheriff.py check-case research/sheriff/SHF-...
```

Cases are written write-once under `crypto-autoresearcher/research/sheriff/`
and published by a PR in that repository. This repository receives only the
fixes its owners choose to make: the sheriff repairs nothing here.
