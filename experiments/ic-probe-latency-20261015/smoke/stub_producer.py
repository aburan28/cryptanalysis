#!/usr/bin/env python3
# Local smoke only: replays archived producer records and holds 600 MB of
# malloc'd memory for 2 s, so the wrapper's page policy and sampler can be
# exercised without the n=83 build. Never evidence.
import json, os, sys, time
recs = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'records.json')))
buf = bytearray(600 << 20)
for i in range(0, len(buf), 4096): buf[i] = 1
time.sleep(2.0)
if os.path.basename(sys.argv[0]).startswith('ic_'):
    t, s = recs['ic']
    open(sys.argv[4], 'w').write(json.dumps(t) + '\n')
    print(json.dumps(s))
else:
    print(json.dumps(recs['rho'][0]))
print('stub env GLIBC_TUNABLES=%s' % os.environ.get('GLIBC_TUNABLES'), file=sys.stderr)
