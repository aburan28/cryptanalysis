# Held polynomial-basis multiplication pilot

`pilot.py` compares two carryless-product prototypes with the exact
polynomial-basis field source from the preceding squaring PR: sparse set-bit
iteration and a 4-bit product table. The curve source is the exact predecessor
snapshot. It uses 12 balanced rounds for 256 field products and three
complete 32-bit scalar calls at degrees 11, 15, 53, and 131. All outputs are
checked against the incumbent.

This was an exploratory, single-seed pilot. Both prototypes regress the
small-field product batch; the 4-bit table is promising only at the larger
degrees. It is held pending a degree-specific candidate, fresh inputs, cold
accounting, and independent confirmation. `run-001.json` retains every paired
sample and the source hashes. No implementation change is promoted here.
