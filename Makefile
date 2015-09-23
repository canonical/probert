#
# Makefile for probert
#
NAME=probert
VERSION=$(shell PYTHONPATH=$(shell pwd) python -c "import probert; print probert.__version__")

version:
	echo "VERSION=$(VERSION)"

$(NAME)_$(VERSION).orig.tar.gz:
	echo "Making tarball"
	fakeroot debian/rules get-orig-source

tarball: $(NAME)_$(VERSION).orig.tar.gz

DPKGBUILDARGS = -us -uc -i'logs*|.coverage|.git.*|.tox|.bzr.*|.editorconfig|.travis-yaml'
deb-src: clean tarball
	@dpkg-buildpackage -S -sa $(DPKGBUILDARGS)

deb-release: tarball
	@dpkg-buildpackage -S -sd $(DPKGBUILDARGS)

deb:
	@dpkg-buildpackage -b $(DPKGBUILDARGS)

clean:
	./debian/rules clean; \
	rm -rf debian/probert; \
	rm -rf ../$(NAME)_*.deb ../$(NAME)_*.tar.gz ../$(NAME)_$.dsc ../$(NAME)_*.changes \
	../$(NAME)_*.build ../$(NAME)_*.upload; \
	wrap-and-sort;

run:
	(PYTHONPATH=$(shell pwd) bin/probert --all)

lint:
	echo "Running flake8 lint tests..."
	flake8 bin/probert --ignore=F403
	flake8 --exclude probert/tests/ probert --ignore=F403

unit:
	echo "Running unit tests..."
	python3 -m "nose" -v --nologcapture --with-coverage probert/tests/
