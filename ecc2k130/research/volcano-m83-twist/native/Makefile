# x86-64 (PCLMUL) port of the volcano-m83 F_(2^83) curve arithmetic, see f83x.c.
CC ?= cc
CFLAGS ?= -O3 -march=native -mpclmul -Wall -Wextra -std=gnu11

f83x: f83x.c
	$(CC) $(CFLAGS) -o $@.tmp f83x.c && mv -f $@.tmp $@

clean:
	rm -f f83x
.PHONY: clean
