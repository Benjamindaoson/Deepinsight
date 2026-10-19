.PHONY: run smoke test

run:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1

run-offline:
	./scripts/run.sh

smoke:
	./scripts/smoke_test.sh

test:
	cd app && ./.venv/bin/python -m pytest -q
