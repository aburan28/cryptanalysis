"""Derive the W18 all-seed native oracle from the audited W15 implementation."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "n131_w15_allseed_inverse_20261011/native.cpp"
DESTINATION = HERE / "native.cpp"


def main():
    source = ORIGINAL.read_text()
    changes = (
        ("// Invert a W15 pair-output", "// Invert a W18 pair-output"),
        ("uint16_t", "uint32_t"),
        ("std::array<Fe,15>", "std::array<Fe,18>"),
        ("std::array<uint32_t,15>", "std::array<uint32_t,18>"),
        ("std::array<uint8_t,15>", "std::array<uint8_t,18>"),
        ("i<15", "i<18"),
        ("rank!=14", "rank!=17"),
        ("32768", "262144"),
        ("32767", "262143"),
        ("16441", "131307"),
    )
    for old, new in changes:
        assert old in source, old
        source = source.replace(old, new)
    assert "W15" not in source
    assert "uint16_t" not in source
    assert "32768" not in source
    with DESTINATION.open("x") as stream:
        stream.write(source)
    print(DESTINATION)


if __name__ == "__main__":
    main()
