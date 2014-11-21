ENV=$(CURDIR)/.env
PYTHON=$(ENV)/bin/python

all: $(ENV)

.PHONY: help
# target: help - Display callable targets
help:
	@egrep "^# target:" [Mm]akefile


.PHONY: test
# target: test - Run tests
test:
	@$(PYTHON) -m unittest discover


.PHONY: test_ci
# target: test_ci - Run tests command adapt for CI systems
test_ci:
	@python -m unittest discover


$(ENV): requirements.txt
	virtualenv --no-site-packages $(ENV)
	$(ENV)/bin/pip install -r requirements.txt
