package main

import (
	"bufio"
	"io"

	ca "github.com/aburan28/cryptanalysis/bindings/go"
)

// newLineScanner reads whole check-in lines, which are longer than
// bufio's default limit.
func newLineScanner(r io.Reader) *bufio.Scanner {
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64<<10), ca.LineMax)
	return sc
}
