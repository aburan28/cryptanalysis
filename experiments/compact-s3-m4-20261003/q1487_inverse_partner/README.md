# Q1487: inverse S3 partner support

The [pre-registered design](design_protocol.json) tests an exact alternative
to Q1486's bounded pair enumeration. In characteristic two,
`S3(x,y,u)=0` is symmetric. Once a midpoint `u` and one nonzero leaf `x`
are fixed, there are at most two possible partner `y` values. Q1487 will
scan the smaller partial leaf domain and test those roots against the other
leaf's complete cyclic-window membership rule. The zero-midpoint case has
one partner, `y=1/x`.

This can check a much larger pair domain while enumerating at most 4,096
anchor values. The experiment must show whether the improved support test
changes the unpinned and ordinary N53/N83 outcomes; no relation recovery
or scaling improvement is assumed. The six CNFs, public targets, actual
factor bases, and window maps are inherited byte for byte from Q1482/Q1486.
The proposal keeps `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. Its exact stage IDs use actual usable point counts,
not nominal window dimensions:

- `PS1N53Ckb1fb430360PDP4hybridh2a52e8f4da45` (`B=430360`, `K=4060`)
- `PS1N83Ckb1fb348006384PDP4hybridhdc30312c79f8`
  (`B=348006384`, `K=2096424`)

The [frozen protocol](protocol.json) binds the source and binary, the
checked Sage runtime, both exact curve/field records, inherited target
and CNF hashes, window selector maps, decision policy, and time limits.
The [small-field control](small_field_validation.json) compared 326,432
ordered domain-pair/midpoint states with direct `S3` evaluation over
`F_32`, including the zero-midpoint reciprocal. The
[native control](native_validation.json) compared direct and inverse
support in 16 N53 and 20 N83 domain/midpoint cases, including partner
domains larger than the 4,096-anchor cap and assigned nonzero leaf bits.
These are equivalence checks; they do not measure ordinary-query yield.
No complete N131 `2^x` follows from the protocol.

## Reproduce custody checks

```sh
python3 experiments/compact-s3-m4-20261003/q1487_inverse_partner/build.py --check
python3 experiments/compact-s3-m4-20261003/q1487_inverse_partner/validate_native.py --check
python3 experiments/compact-s3-m4-20261003/q1487_inverse_partner/freeze_protocol.py --check
```

After the six frozen runs, replay the public-point checks and archive
audit with the checked Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1487_inverse_partner/audit.py --check
```
