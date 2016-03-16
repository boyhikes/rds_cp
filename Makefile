
PROJECT_DIR:=rds_cp
PYTHON_SDIST_DIR?=dist
VENV_DIR?=venv
VENV_ACTIVATE?=$(VENV_DIR)/bin/activate
WITH_VENV?=. $(VENV_ACTIVATE);

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
	CREATE_VENV:=virtualenv --python=python3
endif
ifeq ($(UNAME_S),Darwin)
	CREATE_VENV:=pyvenv
endif

.PHONY: venv
venv: $(VENV_ACTIVATE)
$(VENV_ACTIVATE):
	test -d $(VENV_DIR) || $(CREATE_VENV) $(VENV_DIR)

.PHONY: setup
setup: venv
	$(WITH_VENV) pip install -r requirements_test.txt

.PHONY: dev_setup
dev_setup: setup
	$(WITH_VENV) pip install -r requirements_dev.txt

.PHONY: lint
lint: setup
	$(WITH_VENV) flake8 --exclude __init__.py $(PROJECT_DIR)

.PHONY: clean
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg*/
	rm -rf __pycache__/
	rm -f MANIFEST
	pyclean .

.PHONY: install
install: setup
	$(WITH_VENV) pip install --upgrade .

.PHONY: build
build:
	python setup.py --no-user-cfg sdist --dist-dir $(PYTHON_SDIST_DIR) --formats gztar

.PHONY: teardown
teardown:
	rm -rf $(VENV_DIR)

.PHONY: test
test: install
	# Test the docopt machinery.
	$(WITH_VENV) rds_cp --help > /dev/null
	$(WITH_VENV) nosetests tests

.PHONY: run
run: install
	$(WITH_VENV) rds_cp --force
