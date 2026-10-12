.PHONY: all check clean

all:
	dot -Tsvg destinations.dot -o destinations.svg
	dot -Tpdf destinations.dot -o destinations.pdf
	dot -Tpng -Gdpi=150 destinations.dot -o destinations.png
	python3 render_checks.py
	pandoc REPORT.md --standalone --to latex -V geometry:margin=0.65in -V fontsize=10pt -o report.tex
	pdflatex -interaction=nonstopmode -halt-on-error report.tex
	pdflatex -interaction=nonstopmode -halt-on-error report.tex

check:
	test -s report.pdf
	! rg 'Overfull|undefined references|LaTeX Error' report.log

clean:
	rm -f report.aux report.log report.out
