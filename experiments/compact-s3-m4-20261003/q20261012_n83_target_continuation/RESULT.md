# Q1492: exact N83 target-root continuation exposes a leaf-usability gate

Continuing the Q1491 first-pair sample through the next balanced-S3 link
gave 132 exact root queries on the selected ordinary N83 target. Seventeen
of 40 first pairs had at least one first S3 root; eight pairs had a root
after the target x coordinate entered the second link. The finite set
consumed 10,032 CountedOnb public field API entries for target-conditioned
root queries. On the eight promoted holdout pairs, five had first roots and
two continued, using 2,776 field API entries.

The [protocol](protocol.json) fixes all Q1491 pair receipts and all four raw
preimage x values for each target. The [freeze](freeze.json) binds those files
and the exact S3 oracle source. The [result](result.json) retains every
first-root, target-preimage, and second-root branch, including zero-root
branches. The [validator](validate.py) re-evaluates the S3 polynomial at
every reported root. The curve is `EC1N83Ckb1h876c2921cb64`, B=30,977,592,
K=186,612, `PDP4sat`, `isogeny: "none"`; Q1492 is a stage proposal with null
IC candidate and run IDs.

Q1493 subsequently paired all 40 first pairs on both ordinary targets and
found the same eight surviving pairs. Q1494 checked the exact enumerated
factor base and found those eight were precisely the pairs with both leaves
usable. Thus the observed survival count is a leaf-usability measurement for
this frozen sample, rather than an independent target-dependent yield rate.
The next equation still needs an actual usable second leaf pair and a
verified full four-point relation before a complete N83 or projected N131
solve cost can be fitted.

    env PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_n83_target_continuation/validate.py
