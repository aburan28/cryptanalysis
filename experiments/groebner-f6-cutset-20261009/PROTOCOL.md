# Exact cutset conditioning of width-25 S3 links

The middle S3 links of the four- and five-summand GF(2^9) chains with
seven-bit summand coordinates have 25-variable union support, one above the
current grouped-factor table limit. Fixing the high bit of each nonterminal
middle summand leaves a 24-variable link. This experiment builds the two or
four conditioned static layouts, runs every target through every branch, and
restores the fixed bits before checking the original equations and curve sum.
The 24-variable bag and 200,000,000-state limits remain unchanged.

For an ANF `f` and a Boolean variable `x`, substitution `x=c` is exact:
monomials containing `x` vanish for `c=0`; for `c=1`, they lose `x`; duplicate
resulting monomials cancel modulo two. Consequently,
`f(a)=0` with `a_x=c` iff `f|_(x=c)(a without x)=0`. The assignments of the
unconditioned system are the disjoint union of the restored assignments of
its two branches. The same argument applies to multiple fixed bits. This
requires the conditioned bits to be absent from target-dependent equations;
the driver rejects a target equation that touches one. The method trades a
smaller local bag for `2^(m-3)` branch layouts in these chains and does not
give a general bound independent of the number of middle links.

The frozen cases have field degree 9, curve parameter `b=1`, fixture seed 1,
and summand abscissae `0 <= x < 2^7` in the checked binary-field encoding:

| Summands | Boolean variables | Fixed summand bits | Branches | Max bag | Max states per branch |
| ---: | ---: | --- | ---: | ---: | ---: |
| 4 | 46 | High bit of summand 3 | 2 | 24 | 200,000,000 |
| 5 | 62 | High bits of summands 3 and 4 | 4 | 24 | 200,000,000 |

For each case and both optimized and UBSan grouped-factor builds, enumerate
all 512 target abscissae in ascending order. An independent curve-group
calculation lifts every allowed factor-base abscissa with both signs,
restricts the middle summands to the corresponding branch-bit values, and
enumerates all finite `m`-fold sum abscissae **separately for each branch**.
Each native branch status must equal this comparator. The union of its branch
target sets must equal the unrestricted curve-sum set. Every satisfiable
branch must supply a restored assignment satisfying the original static and
target ANF equations and replaying to the target point. A target is
satisfiable iff at least one branch is satisfiable; an unsatisfiable target
requires every branch to finish unsatisfiable.

The driver also checks ANF conditioning on deterministic random eight-variable
systems by evaluating both sides for every compatible assignment. A fixed
`x+1` equation supplies a restoration control: the conditioned native witness
has `x=0`, while the restored witness must have `x=1` to satisfy the original
equation. A synthetic target equation containing a conditioned bit must be
rejected. The six-summand, seven-bit geometry has 78 Boolean variables and
is retained as an explicit current-ABI limit beyond 64 variables.

Acceptance requires 2 x 2 x 512 = 2,048 complete targets, exactly
`2 x 512 x (2+4) = 6,144` completed native branch queries, all original
equation and point replays, all branch-restricted curve comparisons, and all
applicability controls. Every branch execution is flushed to JSONL. The
compressed report updates after each case and preserves failures or missing
rows as failed status. The complete target-dependent interval begins before
fresh target-equation generation and ends after all branch solves and checks;
source/build setup and independent curve enumeration are separate. Timing is
exploratory until a qualifying isolated-host receipt exists.

From a clean full checkout, run the source-bound grouped-factor build chain
in `.github/workflows/groebner-f6-cutset.yml`, then:

```sh
python3 experiments/groebner-f6-cutset-20261009/validate.py \
  --output /absolute/path/to/new-evidence-directory
```
