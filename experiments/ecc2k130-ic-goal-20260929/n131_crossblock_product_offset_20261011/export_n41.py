"""Export one checked 32-mask N41 source map from the frozen six-block input."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE.parent / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"


def main():
    words = list(map(int, INPUT.read_text().split()))
    assert words[:4] == [1458168294740, 1672312028033, 549756390943, 6]
    pos = 4
    maps = []
    for block in range(6):
        rotation, size = words[pos:pos + 2]
        pos += 2
        assert rotation == block * 5 and size == 64
        columns = {}
        signs = {}
        for _ in range(size):
            x, y, mask, sign, column = words[pos:pos + 5]
            pos += 5
            assert 0 < mask < 64 and 0 <= column < 26 and sign in (0, 1)
            assert x and y
            columns.setdefault(mask, column)
            assert columns[mask] == column
            signs.setdefault(mask, set()).add(sign)
        assert len(columns) == 32 and all(v == {0, 1} for v in signs.values())
        maps.append(columns)
    assert pos == len(words) and all(m == maps[0] for m in maps)
    with (HERE / "support_n41.tsv").open("x") as stream:
        for mask, column in sorted(maps[0].items()):
            stream.write(f"{mask}\t{column}\n")
    print("PASS_N41_SUPPORT_EXPORT")


if __name__ == "__main__":
    main()
