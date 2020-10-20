main.pdf: main.tex compx.tex blur.png
	DOITAGAIN=1;while [ "$$DOITAGAIN" = 1 ]; do pdflatex main; ERROR=$$? ; LOG=$$(grep 'Rerun to get cross-references' main.log|wc -l); if [ "$$ERROR" != 0 ]||[ "$$LOG" -gt 0 ]; then DOITAGAIN=1; else DOITAGAIN=0; fi; done
clean:
	rm -f main.aux main.log main.nav main.snm main.toc
distclean: clean
	rm -f main.pdf
commit: main.tex compx.tex blur.png Makefile README.md .gitignore
	git add $^
	echo "git commit -m '...'"
package.zip: main.tex compx.tex blur.png main.pdf Makefile README.md
	mkdir package && cp $^ package/ && zip -r package package && rm -rf package

.PHONY: clean distclean commit

