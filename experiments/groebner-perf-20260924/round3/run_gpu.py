"""Record content hashes and preserve the complete Metal experiment outcome."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
paths = [HERE / 'tiled_rref.mm', HERE / 'tiled_rref.metal', HERE / 'matrices.json',
         HERE / 'build/tiled-rref', Path('/var/tmp/sage-10.9-current/local/lib/libm4ri.dylib'), Path(__file__)]
command = [str(HERE/'build/tiled-rref'), str(HERE/'tiled_rref.metal'), str(HERE/'matrices.json')]
record = {'command': command, 'load_start': os.getloadavg(), 'start_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
          'scope': 'Internal GF(2) matrix diagnostic, not final relation LA or complete DLP cost',
          'complete_dlp_cost': None, 'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
(HERE/'results/gpu-run.json').write_text(json.dumps(record, indent=2)+'\n')
with (HERE/'results/gpu-tiled.json').open('w') as output, (HERE/'results/gpu-tiled.log').open('w') as errors:
    try:
        result = subprocess.run(command, stdout=output, stderr=errors, timeout=240)
        record['status'] = 'PASS' if result.returncode == 0 else 'failed'
        record['returncode'] = result.returncode
    except subprocess.TimeoutExpired:
        record['status'] = 'timeout'
record['load_end'] = os.getloadavg()
record['end_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
(HERE/'results/gpu-run.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
raise SystemExit(0 if record['status'] == 'PASS' else 1)
