#
# Makefile for probert
#
run:
	(PYTHONPATH=$(shell pwd) bin/probert --all)

lint:
	echo "Running flake8 lint tests..."
	flake8 bin/probert --ignore=F403
	flake8 --exclude probert/tests/ probert --ignore=F403

unit:
	echo "Running unit tests..."
	python3 -m "nose" -v --nologcapture --with-coverage probert/tests/
