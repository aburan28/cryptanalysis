#!/bin/bash
# callgrind instruction counts per profiler variant on a small constructed base (diagnostic)
S=/tmp/claude-0/-home-user/554f08b7-7deb-5c54-8751-f6b3ef70d9ee/scratchpad
B=$S/cargo-target/release/ic_probe_profile_r770
cd $S/prof
for v in ${VARIANTS:-0 1 2 3 4}; do for r in 1 2; do
  env -i PATH=/usr/bin:/bin LC_ALL=C KIC_PROBE_PROFILE=200:$r:$v valgrind --tool=callgrind --collect-atstart=no '--toggle-collect=*probe_profile*' --callgrind-out-file=cg_${v}_${r}.out $B construct:83:1:40 w11.jsonl 7 /dev/null > cgsum_${v}_${r}.json 2> cgerr_${v}_${r}.txt
  echo "$v $r $(grep -h '^summary:' cg_${v}_${r}.out) $(python3 -c "import json;print(json.load(open('cgsum_${v}_${r}.json'))['probes'])" 2>/dev/null)"
done; done
