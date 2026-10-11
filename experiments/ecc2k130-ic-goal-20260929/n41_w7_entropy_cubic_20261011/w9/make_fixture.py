"""Retain the frozen public witness and replace only its source-column map."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PRIOR=HERE.parent.parent/"n41_transport_cubic_s8_20261011/fixture.json"
geometry=json.loads((HERE/"geometry.json").read_text())
prior=json.loads(PRIOR.read_text())
columns={row["mask"]:row["column"] for row in geometry["rows"]}
assert len(columns)==259
assert all(mask in columns for mask in prior["known_masks"])
prior["status"]="W9_SOURCE_EXTENDS_VERIFIED_TRANSPORTED_PUBLIC_WITNESS"
prior["mask_columns"]={str(k):v for k,v in columns.items()}
prior["known_columns"]=[columns[m] for m in prior["known_masks"]]
assert len(set(prior["known_columns"]))==8
prior["w9_geometry_sha256"]=hashlib.sha256((HERE/"geometry.json").read_bytes()).hexdigest()
prior["w6_fixture_sha256"]=hashlib.sha256(PRIOR.read_bytes()).hexdigest()
(HERE/"fixture.json").write_text(json.dumps(prior,indent=2,sort_keys=True)+"\n")
print(prior["status"],len(columns),len(set(columns.values())))
