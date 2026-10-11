"""Convert exact tuple counts to full-curve mean ceilings using cofactor four."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    source = HERE / "support_result.json"
    data = json.loads(source.read_text())
    rows = []
    for item in data["rows"]:
        order = int(item["subgroup_order"])
        cells = {}
        for k in ("8", "9"):
            tuples = int(item["signed_ordered_distinct_column_tuples"][k])
            mean = Fraction(tuples, 4 * order)
            cells[k] = {"raw_curve_order": str(4 * order),
                        "labeled_mean_upper_ceiling": str(mean),
                        "decimal": format(float(mean), ".9g")}
        rows.append({"label": item["label"], "pair_slots": cells})
    result = {"status": "PASS_COFACTOR_FOUR_SOURCE_CEILINGS",
              "basis": "exact distinct-column signed tuples divided by full curve order 4r",
              "scope": "uniform full-curve average upper ceiling; not a fixed-target yield estimate",
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "rows": rows}
    with (HERE / "support_interpretation.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    for row in rows:
        print(row["label"], row["pair_slots"]["9"]["decimal"])


if __name__ == "__main__":
    main()
