"""Install only the changed Python module into the local Sage fork."""
import hashlib
import json
import shutil
from pathlib import Path

from sage.schemes.elliptic_curves import binary_hardware

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FORK = ROOT / 'third_party/sage-binary'
SOURCE = FORK / 'src/sage/schemes/elliptic_curves/binary_hardware.py'
TARGET = Path(binary_hardware.__file__).resolve()
OUT = HERE / 'install-001'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


intent = json.loads((HERE / 'intent-candidate-v1.json').read_text())
if not TARGET.is_relative_to((FORK / 'local').resolve()):
    raise RuntimeError('refusing to install outside the local Sage fork')
if digest(TARGET) != intent['incumbent_hardware_source_sha256']:
    raise RuntimeError('installed incumbent source does not match frozen intent')
OUT.mkdir(exist_ok=False)
shutil.copy2(TARGET, OUT / 'previous-installed-binary_hardware.py')
shutil.copyfile(SOURCE, TARGET)
(OUT / 'install.json').write_text(json.dumps({
    'source': str(SOURCE), 'source_sha256': digest(SOURCE),
    'target': str(TARGET), 'installed_sha256': digest(TARGET),
    'previous_sha256': intent['incumbent_hardware_source_sha256'],
}, indent=2) + '\n')
print('Installed auto-routing candidate', digest(TARGET)[:12])
