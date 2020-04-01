#
# Makefile for probert
#
NAME=probert
VERSION=$(shell PYTHONPATH=$(shell pwd) /usr/bin/env python3 -c "import probert; print(probert.__version__)")
.PHONY: all version tarball test $(NAME)_$(VERSION).orig.tar.gz

all: run

version:
	echo "VERSION=$(VERSION)"

../$(NAME)_$(VERSION).orig.tar.gz:
	echo "Making tarball"
	fakeroot debian/rules get-orig-source

tarball: ../$(NAME)_$(VERSION).orig.tar.gz

DPKGBUILDARGS = -i'logs*|.coverage|.git.*|.tox|.bzr.*|.editorconfig|.travis-yaml'
deb-src: tarball
	@dpkg-buildpackage -S -sa $(DPKGBUILDARGS)

deb-release: tarball
	@dpkg-buildpackage -S -sd $(DPKGBUILDARGS)

deb:
	@dpkg-buildpackage -b -us -uc $(DPKGBUILDARGS)

clean:
	./debian/rules clean; \
	rm -rf debian/probert; \
	rm -rf ../$(NAME)_*.deb ../$(NAME)_*.tar.gz ../$(NAME)_$.dsc ../$(NAME)_*.changes \
	../$(NAME)_*.build ../$(NAME)_*.upload; \
	wrap-and-sort;

run:
	(PYTHONPATH=$(shell pwd) bin/probert --all)

test:
	tox
