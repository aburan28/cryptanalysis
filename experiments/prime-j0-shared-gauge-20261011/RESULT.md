# Shared gauge and window orientation screen

The three tau buckets can use one common omega frame. For the set
`S_e` of unit powers present in bucket `e`, accumulating those powers
needs `|S_e|-1` frame transitions. Ending all nonempty buckets in a
common frame `g` requires one more rotation for each bucket without
`g`; returning the final point to frame zero requires one rotation
when `g != 0`. Thus the exact rotation count is

`sum_e (|S_e|-1 + [g not in S_e]) + [g != 0]`,

where empty buckets contribute zero. Taking the minimum over three
frames preserves the point because omega commutes with tau. The
[design-panel screen](screen.json) verified the existing quotient
count of 16,546 rotations and lowered it to 16,273 on the same
4,096 scalars. The budgeted direct format moved from 17,500 to
17,132, and the minimum direct format from 18,207 to 17,817.
These are operation counts; no native candidate or timing has been
promoted from this screen.

Pre-rotating each window's point table by a fixed power of omega and
subtracting that power from its runtime unit code preserves every
point while changing the bucket power sets. The
[orientation screen](orient-screen.json) fit 13 window powers on the
first 2,048 quotient scalars and evaluated the remaining 2,048
separately. It reduced the shared-frame count by 150 in training but
only 23 in validation (8,130 to 8,107). The fixed-frame comparison
was 8,266 to 8,262 in validation. The orientation fit is therefore
not carried into a native candidate.

The [seed-image census](alternate-screen.json) enumerated all
admissible tau images of the 83,051 existing full-window seeds.
It found 39,615 classes with more than one representation, but no
class with an alternative of lower tau exponent than its assigned
one. Choosing these alternatives cannot reduce the assigned tau
depth. The next candidate instead changes the orbit index itself.
