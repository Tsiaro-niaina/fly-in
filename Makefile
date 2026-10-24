VENV = .venv
PYTHON = $(VENV)/bin/python
STAMP = $(VENV)/.installed
MAIN = main.py
MAP ?= maps/hard/03_ultimate_challenge.txt
ARGS ?=

.PHONY: install run gui debug clean fclean lint lint-strict test

$(STAMP): requirements.txt
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -r requirements.txt
	touch $(STAMP)

install: $(STAMP)

run: $(STAMP)
	@$(PYTHON) $(MAIN) $(MAP) $(ARGS)

gui: $(STAMP)
	@$(PYTHON) $(MAIN) $(MAP) --gui $(ARGS)

debug: $(STAMP)
	@$(PYTHON) -m pdb $(MAIN) $(MAP) $(ARGS)

test: $(STAMP)
	@$(PYTHON) -m pytest

clean:
	@find . -path ./$(VENV) -prune -o -type d -name __pycache__ -exec rm -rf {} +
	@rm -rf .mypy_cache .pytest_cache

fclean: clean
	@rm -rf $(VENV)

lint: $(STAMP)
	@$(VENV)/bin/flake8 .
	@$(VENV)/bin/mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict: $(STAMP)
	@$(VENV)/bin/flake8 .
	@$(VENV)/bin/mypy . --strict
