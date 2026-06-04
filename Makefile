.PHONY: up down status ask research eval eval-calibrate serve web web-install format format-check lint typecheck test ci

up:
	python3 scripts/devstack.py up

down:
	python3 scripts/devstack.py down

status:
	python3 scripts/devstack.py status

ask:
	@test -n "$(Q)" || { echo 'usage: make ask Q="your question"'; exit 1; }
	uv run argus "$(Q)"

research:
	@test -n "$(Q)" || { echo 'usage: make research Q="your question"'; exit 1; }
	uv run argus --deep "$(Q)"

migrate:
	uv run argus migrate

eval:
	uv run argus eval

eval-calibrate:
	uv run argus eval --calibrate

serve:
	uv run argus serve --reload

web-install:
	cd frontend && bun install

web:
	bash scripts/web.sh

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
