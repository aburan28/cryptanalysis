#!/bin/sh
# ca volcano --census-out / --edges-out on the whole 2-volcano of curve C of the
# aburan28/crypto volcano-rho study (ramified crater, depth 3, 2 + 4 + 8 + 16
# vertices): 30 vertex lines, 14+... directed edges, every level count right.
set -eu
CA=${1:?path to ca}
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT
"$CA" volcano --p 146833024135393 --a 14391545271884 --b 141956518099848 --ell 2 \
    --radius 8 --max-vertices 1000 --trials 1 --per-level 0 --controls 0 \
    --ks 5,7 --census-out "$D/v.jsonl" --edges-out "$D/e.jsonl" > "$D/r.json"
test "$(wc -l < "$D/v.jsonl")" -eq 30
for lv in 0:2 1:4 2:8 3:16; do
    l=${lv%%:*}; c=${lv##*:}
    test "$(grep -c "\"level\":$l," "$D/v.jsonl")" -eq "$c"
done
# 29 tree edges + 1 crater edge = 30 undirected = 60 directed minus floor edges
# going nowhere: every vertex's own kernels are listed, so count the tree flag.
test "$(grep -c '"tree":true' "$D/e.jsonl")" -eq 29
test "$(grep -c '"model_match":true' "$D/e.jsonl")" -eq 29
test "$(grep -c '"to":-1' "$D/e.jsonl")" -eq 0
grep -q '"hk":\["' "$D/v.jsonl"
grep -q '"controls":\[{"u":' "$D/v.jsonl"
grep -q '"edges_verified":29' "$D/r.json"
echo ok
