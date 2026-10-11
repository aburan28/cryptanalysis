"""Build an all-seed replay with the opposite GF(2) pivot convention."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "native.cpp"
DESTINATION = HERE / "native_lowpivot.cpp"


def main():
    source = SOURCE.read_text()
    insertion = """static int lowest_bit(Fe value) {
    if(value.lo) return __builtin_ctzll(value.lo);
    if(value.mid) return 64 + __builtin_ctzll(value.mid);
    if(value.hi) return 128 + __builtin_ctzll(value.hi);
    return -1;
}

"""
    assert source.count("struct LinearInverse {") == 1
    source = source.replace("struct LinearInverse {", insertion + "struct LinearInverse {")
    changes = (
        ("int bit_index=highbit(value);", "int bit_index=lowest_bit(value);"),
        ("for(int i=130;i>=0;--i)if(!zero(pivot[i]))", "for(int i=0;i<=130;++i)if(!zero(pivot[i]))"),
    )
    for old, new in changes:
        assert source.count(old) == 1
        source = source.replace(old, new)
    with DESTINATION.open("x") as stream:
        stream.write(source)
    print(DESTINATION)


if __name__ == "__main__":
    main()
