# Held Metal per-element kernel experiment

The installed Sage code is unchanged. This archive compares the current
one-thread-per-output-word Metal map with a one-thread-per-field-element
prototype. Both return ordinary Sage points through the explicit batching
API from the preceding PR. CPU batching and native Sage Frobenius are paired
controls. All measured outputs were compared with native Sage points.

`pilot-001/` used a dynamic local accumulator array in the element kernel.
`candidate-v1/` preserves that exact source and frozen intent. The second
candidate in `source/` generates fixed word accumulators and a fixed byte
loop for each field degree. `pilot-002/` tested that revision, and
`confirm-001/` tested independent seeds and a larger batch. The bridge in
`source/binary_hardware_metal.mm` dispatches one thread per element. The
standalone library was built under `/private/tmp`, with source and binary
hashes frozen before both pilots; it was never installed into Sage.

The portable receipt check is:

```sh
python3 experiments/sage-ic-campaign/metal-element-kernel-20260924/verify_archive.py
```

The experiment is held. No Sage patch is proposed from these kernels. See
`RESULT.md` for the complete-call measurements and the next test site.
