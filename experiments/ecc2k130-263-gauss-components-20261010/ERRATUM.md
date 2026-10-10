# Correction to the preliminary component label

The preregistered [protocol](PROTOCOL.md) says the larger raw native-XOR
components were dominated by projective-S3 inputs. That phrase came from a
read-only exploratory parser that used a signed named target literal directly
as a Python list index. Negative literals then indexed unrelated components.

The committed analyzer was corrected in `f5379b0cc` **before** the component
receipts and eight solver inputs were frozen in `92d79d10f`. It uses the
absolute variable ID for each named literal. Its independently rehashed
[source](runs/R1/source.components.json) and
[descendant](runs/R1/descendant_native.components.json) inventories show:

- The largest raw components have 27,604 and 27,759 variables, respectively,
  and contain no named input variables. Their internal auxiliary-gate origin
  is not identified by this graph alone.
- Each selector component has 7,524 variables, 7,380 native-XOR lines, and
  all 144 named selector bits. It ranks 23rd by raw component size on each
  curve.

The frozen solver question and matrix policies did not change. The
`selector_window` transcript independently confirms that CryptoMiniSat
selected a 7,380 × 7,524 matrix on both curves. The original protocol commit
is retained; this note corrects only the explanatory classification, without
rewriting the experiment or its input hashes.
