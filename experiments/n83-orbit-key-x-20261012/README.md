# Canonical x lookup from packed N83 orbit keys

The width-16 geometric base contains 32,648 packed signed-Frobenius orbit
keys. The existing point-decomposition setup reconstructs a field point
from every key and applies all 83 Frobenius powers to obtain its smallest
ONB x coordinate. The cycle-table lookup computes the same value directly
from the packed key's x half. It rotates the 83 cycle-coordinate bits and
uses precomputed eight-bit inverse-permutation tables to recover each ONB
coordinate candidate. The y half of the key is unnecessary for this lookup.
The [materializer](materialize.py) writes the complete 11-byte-per-key x
array in the same sorted key order, with its digest tied to both independently
computed arrays. A future runner can load this target-independent cache
without rebuilding canonical x values.

The complete 32,648-key check returned `PASS`: every canonical x matched,
and all 32,648 outputs were distinct. The reference pass took 403.872
seconds and the cycle-table pass took 22.735 seconds in the same process,
an exploratory 17.76-fold setup-path ratio. The run overlapped another
solver on the shared host, so this is an algorithmic diagnostic and cache
correctness result, not an isolated CPU speedup measurement. The public
cache is 359,128 bytes, compared with repeated field-point reconstruction
and 83 field Frobenius evaluations per key in the existing setup path.

The [full-base protocol](protocol.json) fixes the exact width-16 key file,
its independent Sage geometry replay, the old and new source hashes, and
the order `reference` then `cycle_table`. The [runner](run.py) compares the
two outputs for every key, checks that canonical x values remain distinct,
and hashes both ordered output arrays. CPU wall times on this shared host
are exploratory; exact equality on the complete base is the acceptance
criterion for this setup-path change.

The source is [fast_x.py](fast_x.py). For a packed canonical orbit key,
the high 83 bits are one cyclic representative of the projected point's
x coordinate. Rotating those bits traverses precisely the Frobenius orbit
in cycle coordinates. Inverting the coordinate permutation for each
rotation and taking the integer minimum therefore matches the existing
`min(toCoords(Frobenius^j(x)))` value.

Reproduce through the checked repository Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-orbit-key-x-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-orbit-key-x-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-orbit-key-x-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-orbit-key-x-20261012/materialize.py
python3 experiments/n83-orbit-key-x-20261012/verify.py
```

The runner refuses to overwrite a terminal result. Reproduce in a fresh
directory with the supplied frozen key file and protocol.
