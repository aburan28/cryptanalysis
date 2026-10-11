.PHONY: all render check clean

all: render

# This renderer lays out recorded results; it does not run any research code.
render:
	dot -Tsvg transfer.dot -o transfer.svg
	dot -Tpng -Gdpi=145 transfer.dot -o transfer.png
	dot -Tpdf transfer.dot -o transfer.pdf
	python3 -c "from pathlib import Path; import fitz; doc = fitz.open(stream=Path('counts.svg').read_bytes(), filetype='svg'); doc[0].get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False).save('counts.png'); Path('counts.pdf').write_bytes(doc.convert_to_pdf())"
	pandoc REPORT.md --standalone --to latex --lua-filter=report.lua -V geometry:margin=0.7in -V fontsize=10pt -o report.tex
	pdflatex -interaction=nonstopmode -halt-on-error report.tex
	pdflatex -interaction=nonstopmode -halt-on-error report.tex

check:
	test -s report.pdf
	! rg 'Overfull|undefined references|LaTeX Error' report.log

clean:
	rm -f report.aux report.log report.out
