.PHONY: dev test lint

dev:
	uvicorn lawrence_kernel.main:app --reload --app-dir services/kernel --host 127.0.0.1 --port 8000

test:
	pytest -q

lint:
	python -m compileall services/kernel/lawrence_kernel
