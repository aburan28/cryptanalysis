# First local panel interruption

The first frozen six-arm attempt completed five rows. Candidate row 2 exited
with code 101 while writing its JSON result: `StorageFull`, OS error 28,
`No space left on device`. Its zero-byte result, run record, and native
stderr are preserved in this directory along with the five completed rows.
The panel was not used for aggregate timing or correctness promotion.
