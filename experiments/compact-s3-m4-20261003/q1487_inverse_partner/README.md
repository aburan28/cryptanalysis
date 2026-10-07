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
`isogeny: "none"`; exact `PS1` stage IDs will be frozen after implementation.
No complete N131 `2^x` follows from this design.
