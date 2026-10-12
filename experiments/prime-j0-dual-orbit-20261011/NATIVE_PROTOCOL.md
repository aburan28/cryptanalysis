# Folded norm-seven native candidate

The first native candidate uses the `rho0` cover: the maps are
`1`, `tau`, `tau^2`, and `rho=1+tau`. It stores 67,338 affine seeds in
each of twelve full radix-1024 windows and reuses the existing exact
terminal atlas. Its charged table comprises 817,344 affine entries.

Let `B0`, `B1`, `B2`, and `R` be the four buckets after the six-unit
actions. Evaluate

`(B0+R) + tau((B1+R) + tau(B2))`.

This equals `B0+tau(B1)+tau^2(B2)+rho(R)`. It uses the existing two
outer tau maps and adds two projective bucket merges when `R` is
nonidentity. All table construction, digit recoding, and point checks
must include the terminal window and every map tag.

Freeze the atlas materializer and the fresh 4,096-scalar input law
before generating their artifacts. The scalar panel must be disjoint
modulo the subgroup order from earlier panels in the law's source list.
Check every native result against an existing exact implementation,
and the first 128 independently by binary multiplication. Run the
complete native suite and edge replay. Record code, atlas, input,
binary, and host receipts. A timing comparison requires the separate
host isolation gate and a paired same-input protocol.
