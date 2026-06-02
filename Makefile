.PHONY: up down status ask format format-check lint typecheck test ci

up:
	python3 scripts/devstack.py up

down:
	python3 scripts/devstack.py down

status:
	python3 scripts/devstack.py status

ask:
	uv run argus "$(Q)"

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

typecheck:
	uv run ty check

test:
	uv run pytest

ci: format-check lint typecheck test
