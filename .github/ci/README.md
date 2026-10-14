# CI routing and execution budgets

Public run history inspected on 2026-10-11 shows a runner backlog rather than
slow C unit tests. The latest 100 PR runs contained 70 queued runs and 30
cancelled runs. In successful C CI run
[38155267701](https://github.com/aburan28/cryptanalysis/actions/runs/38155267701),
the slowest job (Valgrind) executed for about 1.82 minutes; the jobs waited about
346 minutes for runners. These are observations from those samples, not a
prediction for every check. Timeouts limit execution after a runner starts;
they cannot limit GitHub's queue delay.

The repository has 115 workflows, including many independent research replay
checks. Feature branches now validate through `pull_request`; ordinary pushes
validate the actual default branch, `claude/cryptanalysis-repo-setup-p59kek`.
Release tag patterns, manual runs, schedules and archive/offsite maintenance
retain their triggers. If the default branch changes, update these branch
patterns as part of that change. Event-specific concurrency cancels superseded
PR runs without a push cancelling a PR or merge-group run.

## Scope policy

`scopes.json` selects jobs in 57 workflows that previously ran for all changes
or watched the entire Groebner campaign. `scripts/ci_scope.py` uses a complete
local Git diff, including deleted files and both sides of a rename. A multi-
commit push compares against its recorded `before` SHA, a PR compares against
the checked merge commit's first parent, and a merge group compares against its
recorded base SHA. Missing bases, failed fetches and unknown events run all
jobs. There is no GitHub changed-files API limit.

Examples:

| Change | Work that remains relevant |
| --- | --- |
| Root README, agent instructions, unrelated docs or paper PDF | No C build, bindings, suite, fuzz or Groebner replay |
| C sources, public headers or CMake configuration | C validation and bindings/suite that compile or consume the C library |
| Go bindings | Go validation and the Go CodeQL scan |
| Python index-calculus engine | Python engine validation and Python CodeQL |
| CUDA kernels or their build scripts | CUDA compilation and consuming crates |
| A new Groebner round | Its own checks; older rounds do not rebuild for an unrelated newer round |
| Frozen proof fixtures, protocol JSON, polynomial code or archive data | Their existing scientific/evidence checks |

Groebner generators contain dynamically selected historical round numbers, so
the scope conservatively includes every prior round through the newest round
referenced by that workflow. It also includes shared campaign helpers,
polynomial arithmetic and external experiment directories used by the workflow.
Do not remove those paths just because they look like result data: they can be
inputs to independent proof replay or source-custody checks. When adding a new
cross-round dependency, update that workflow's scope in the same change.

Scope changes and the shared selector are infrastructure changes and select
all configured jobs. Existing narrowly filtered workflows keep their filters.
The 29 previously unfiltered workflows still trigger for every PR and merge
group; their irrelevant work is skipped within the workflow. Matrix jobs gate
each step, because GitHub evaluates a job's `if` before expanding its matrix.
This retains existing check names. Only an explicit boolean `false` permits a
skip; missing selector outputs run the work, and invalid JSON fails the check.
An unsuccessful selector also runs the work. Cancelled workflows do not start
new dependent builds; retained-artifact steps still run for an actual failure.

## Budgets and evidence

Automatic PR and merge-group jobs have at most a 25-minute execution budget;
jobs that previously inherited GitHub's six-hour default now have an explicit
20-minute limit. Existing smaller budgets stay smaller. Longer original
budgets remain available to manual runs, schedules and post-merge validation.
The three-repetition initial-batch profiling steps run after merge or by manual
dispatch. PRs still build the matched engines and independently audit the
frozen reference, batched proofs and large proof. No certificate or archive
gate is made advisory, and no benchmark protocol or historical result is edited.

These budgets need observation on actual hosted runners, especially for cold
research builds; a timeout remains a failure. Routing tests and workflow lint
validate the configuration, not a claim that every research replay was run or
that the live backlog has cleared. Actual branch protection/required-check
settings need authenticated access and were unavailable during this audit.

Validate changes with:

```sh
python3 -m unittest discover -s tests -p test_ci_scope.py -v
actionlint -shellcheck= -pyflakes= .github/workflows/*.yml
```
