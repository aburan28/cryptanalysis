# Weak-curve criteria provenance

`criteria.json` and `attack_map.json` are byte-for-byte snapshots from
`aburan28/crypto`, commit `2f1f9c553b4b2f03643f4200d6e12ab9221900c4`,
under `research/weak_curve_leaderboard_20261012/`.

| File | SHA-256 | Git blob |
| --- | --- | --- |
| `criteria.json` | `165fc26fa90f1789e3fe01301cda59c8fd2df1a3219fe5ba9cfc97397148ba93` | `f590ff37440a30d77f0513dff227d402beef5b51` |
| `attack_map.json` | `3316d2b821a9f4be9fbd43c538a88a26877370283dbd07acdae4fcbb26dd1935` | `802572c1e147ea2afe32a04ad60b680cb254e5e4` |

The binary embeds both files and reports their hashes with every audit. The
catalog describes methods, domains and required witnesses. A listed criterion
is not itself a finding on the supplied curve. Updates should copy a reviewed
upstream revision, refresh these hashes, and retain the previous revision in
Git history. Mathematical statements and evidence grades stay distinct.
