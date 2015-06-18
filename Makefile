#
# Makefile for probert
#
run:
	(PYTHONPATH=$(shell pwd) bin/probert)

make lint:
	echo "Running flake8 lint tests..."
	flake8 bin/probert --ignore=F403
	flake8 --exclude probert/tests/ probert --ignore=F403

make unit:
	echo "Running unit tests..."
	/usr/bin/nosetests -v --nologcapture --with-coverage probert/tests/
