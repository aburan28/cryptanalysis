# Compression and refill reaches 6,094 rho-only classes

A fixed-size radix-1024 scalar cover now uses **67,338 seeds** and requires
the norm-seven map for **6,094 of 174,764 classes**. The exact tau-only lower
bound at this budget is **6,079**, leaving a gap of **15 classes**. The
preceding redundant-slot cover uses 6,194 rho-only classes at the same seed
count, so compression and refill eliminate another **100**.

The [constructor](augment.py) replaces two selected seeds by one whose
four-map offers preserve complete coverage, then spends the freed slot on a
seed that adds tau providers. It ranks the resulting two-for-two exchanges
by their exact reduction in rho-only classes, rechecks coverage and the
objective after every accepted move, and records the ordered path. The first
pass accepted 100 moves; a complete second scan found no further improving
move of this form. The final cover SHA-256 is
`f5a88df0b9e08f39d2af4e8747cb1971c85b6afac94d652dfa55dbafb59b5261`.

The [independent verifier](verify.py) replays all 100 exchanges with
separately implemented Eisenstein actions, checks the intermediate
two-for-one coverage condition, reconstructs the priority atlas, and checks
all **1,048,576 residues**. Its [receipt](check.json) passed and binds the
source, path, input cover, and final cover hashes.

The exact class count is a construction result. A fresh scalar panel, native
point replay, and controlled wall-time experiment are subsequent checks for
this cover. The previous panel was used to design the earlier cover and is
not a holdout for this variant.
