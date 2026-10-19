.PHONY: run smoke test

run:
	./scripts/run.sh

smoke:
	./scripts/smoke_test.sh

test:
	cd app && ./.venv/bin/python -m pytest -q
