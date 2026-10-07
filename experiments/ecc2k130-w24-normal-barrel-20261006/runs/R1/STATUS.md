# R1 disposition: schema incomplete

R1 ran the frozen 120-input/1,200-rotation panel under implementation commit
`8b3408ec11470e55bfe7c36b7902efeacc2e7cad`. Its producer, independent
Sage replay, and two mutations passed. On receipt review, the result omitted
the **full 131-column polynomial-to-normal conversion matrix and its hash**.
It archived only the 24-column W24-seed-to-normal map and the full
normal-to-polynomial map. The protocol explicitly calls for both full basis
conversions. Preserve R1 as raw evidence, but do not use it as the accepted
gate. R2 adds the missing matrix and independent check under a new code
snapshot; R1's exploratory wall time is not compared to R2 as a speed test.
