# Explicit conductor-prime isogeny tools for the m=83 volcano study (AArch64, PMULL).
CC ?= clang
CFLAGS ?= -O3 -mcpu=apple-m1 -Wall -Wextra -std=c11
BIN := isogeny

all: $(BIN)

$(BIN): isogeny.c tower.c tower.h
	$(CC) $(CFLAGS) -o $@.tmp isogeny.c tower.c && mv -f $@.tmp $@

clbench: clbench.c tower.c tower.h
	$(CC) $(CFLAGS) -o $@.tmp clbench.c tower.c && mv -f $@.tmp $@

clean:
	rm -f $(BIN) clbench

.PHONY: all clean

# Shared libraries are built to a temporary name and renamed, so processes that
# already mapped the old file keep a valid inode (writing in place is SIGBUS).
libcpualarm.dylib: cpualarm.c
	$(CC) -O2 -dynamiclib -o $@.tmp cpualarm.c && mv -f $@.tmp $@

all: libcpualarm.dylib

libf83.dylib: f83.c
	$(CC) -O3 -mcpu=apple-m1 -Wall -Wextra -dynamiclib -o $@.tmp f83.c && mv -f $@.tmp $@

all: libf83.dylib
