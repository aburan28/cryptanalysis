# Q1425 first left-only control attempt

The committed v1 source (`92aeff09c`) was frozen before launching the
N53 `control_preseed` cell. It inserted one exact S3 root lemma for the
known left leaf pair, retained the right-pair and outer S3 links in SAT,
and fixed all four raw leaf coordinates and the target selector. The first
CryptoMiniSat call returned `BOUNDED_UNKNOWN` at the declared 100,000
conflict cap after 5.032211 seconds. The JSONL trace records that call.

The v1 runner incorrectly asserted that every known-solution control
must return a verified relation, so it did not write its terminal JSON
receipt after this censored result. The source snapshot, frozen input
digest, and trace are preserved here. V2 records bounded controls and
preseeds both pair links in its control cells.
