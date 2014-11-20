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


# target: deb - Build deb package
deb: test
	@find . -name '*.pyc'|xargs rm -f
	@debuild clean
	@debuild -i -us -uc -b
	@debuild clean


$(ENV): requirements.txt
	virtualenv --no-site-packages $(ENV)
	$(ENV)/bin/pip install -r requirements.txt
