.PHONY: build clean

PYENV = . env/bin/activate;
PYTHON = . env/bin/activate; python

-include .jira_creds

build: env

install:
	python setup.py develop

clean:
	find jy -name "*.pyc" -type f -exec rm {} \;

nuke: clean
	rm -rf env

test: env
	$(PYENV) nosetests $(NOSEARGS)

debug: env
	$(PYENV) nosetests --pdb --pdb-failures $(NOSEARGS)

shell:
	$(PYENV) ipython

env: env/bin/activate
env/bin/activate: requirements.txt setup.py
	virtualenv --no-site-packages env
	. env/bin/activate; pip install -r requirements.txt
	. env/bin/activate; pip install -e .
	touch $@

# ensure we only update when requirements.txt has changed
upgrade update: env/lib/python2.7/site-packages
env/lib/python2.7/site-packages: env requirements.txt
	. env/bin/activate; pip install -e . -r requirements.txt --upgrade
	# touch ensures we are newer than our targets.
	touch $@
