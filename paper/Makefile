# Makefile for the ECDLP measurement paper.
#
# Targets:
#   make             — build PDF (pdflatex + bibtex)
#   make check       — unresolved refs, overfull boxes, page count
#   make arxiv       — produce arxiv-submission.tar.gz
#   make eprint      — produce eprint-submission.zip
#   make deanonymize — restore author block from AUTHORS
#   make clean       — remove build artefacts (keeps the committed PDF)

TEX     := ecdlp.tex
PDF     := $(TEX:.tex=.pdf)
SECTIONS := sec-intro.tex sec-method.tex sec-rho.tex sec-rho-variants.tex \
            sec-ecc2k-arith.tex sec-ecc2k-gpu.tex sec-ecc2k-fpga.tex \
            sec-ecc2k-campaign.tex sec-indexcalc.tex sec-related.tex \
            app-reproduction.tex
BIB     := ecdlp.bib
AUX     := $(TEX:.tex=.aux) $(TEX:.tex=.log) $(TEX:.tex=.out) $(TEX:.tex=.toc) \
           $(TEX:.tex=.bbl) $(TEX:.tex=.blg) $(TEX:.tex=.lof) $(TEX:.tex=.lot)
ARXIV_TARBALL := arxiv-submission.tar.gz
EPRINT_ZIP    := eprint-submission.zip

.PHONY: all clean arxiv eprint deanonymize check

all: $(PDF)

$(PDF): $(TEX) $(SECTIONS) $(BIB)
	pdflatex -interaction=nonstopmode $(TEX) || true
	bibtex $(TEX:.tex=)
	pdflatex -interaction=nonstopmode $(TEX) || true
	pdflatex -interaction=nonstopmode $(TEX)

clean:
	rm -f $(AUX)
	rm -f $(ARXIV_TARBALL) $(EPRINT_ZIP)
	rm -rf submission-staging/
	rm -f figures/*.aux figures/*.log

# arXiv expects a single .tar.gz with .tex sources, .bib, and figures.
# No PDF (arXiv compiles it server-side).
arxiv: $(TEX) $(SECTIONS) $(BIB)
	mkdir -p submission-staging/arxiv/figures
	cp $(TEX) $(SECTIONS) $(BIB) abstract.txt AUTHORS.example Makefile README.md ic-rerun.txt \
	  submission-staging/arxiv/
	cp -r figures/*.tex figures/*.pdf submission-staging/arxiv/figures/ 2>/dev/null || true
	cd submission-staging/arxiv && tar czf ../../$(ARXIV_TARBALL) *
	rm -rf submission-staging/arxiv
	@echo "arXiv submission bundle ready: $(ARXIV_TARBALL)"

# IACR ePrint accepts PDF + optional source.
eprint: $(PDF)
	mkdir -p submission-staging/eprint
	cp $(PDF) $(TEX) $(SECTIONS) $(BIB) abstract.txt README.md Makefile \
	  submission-staging/eprint/
	cd submission-staging/eprint && zip -q ../../$(EPRINT_ZIP) *
	rm -rf submission-staging/eprint
	@echo "IACR ePrint submission bundle ready: $(EPRINT_ZIP)"

# Restore author block from AUTHORS (for non-anonymous releases).
deanonymize: $(TEX)
	@if [ ! -f AUTHORS ]; then \
	  echo "ERROR: AUTHORS file missing — create it with the author block"; \
	  echo "Example AUTHORS file contents:"; \
	  echo '  \\author{Alice \\and Bob \\\\ Affiliation}'; \
	  echo '  \\date{\\today}'; \
	  exit 1; \
	fi
	@cp $(TEX) $(TEX).anon-backup
	@python3 -c 'import re; \
tex = open("$(TEX)").read(); \
authors = open("AUTHORS").read().strip(); \
tex = re.sub(r"\\author\{Anonymous\}\s*\\date\{\}", authors + "\n", tex, count=1); \
open("$(TEX)", "w").write(tex); \
print("De-anonymized $(TEX); backup saved as $(TEX).anon-backup")'

check: $(PDF)
	@echo "Checking $(PDF)..."
	@if grep -q 'LaTeX Warning: There were undefined references' $(TEX:.tex=.log); then \
	  echo "FAIL: unresolved references"; \
	  grep 'LaTeX Warning: Reference' $(TEX:.tex=.log) || true; \
	  exit 1; \
	else \
	  echo "All references resolved."; \
	fi
	@if grep -qE '(LaTeX|Package natbib) Warning: There were undefined citations' $(TEX:.tex=.log); then \
	  echo "FAIL: unresolved citations"; \
	  exit 1; \
	fi
	@if grep -E 'Overfull \\hbox' $(TEX:.tex=.log); then \
	  echo "FAIL: overfull boxes"; \
	  exit 1; \
	else \
	  echo "No overfull boxes."; \
	fi
	@echo "Page count:"
	@pdfinfo $(PDF) | grep -i pages
	@ls -lh $(PDF)
