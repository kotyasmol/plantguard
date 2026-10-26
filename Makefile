.PHONY: bootstrap test test-python test-web test-migrations lint build up down db-upgrade db-downgrade ksql-init smoke

bootstrap:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements-dev.txt
	npm install

test: test-python test-web

test-python:
	.venv/bin/python -m pytest

test-web:
	npm run test --workspace @plantguard/web

test-migrations:
	@trap 'docker compose -p plantguard-migrations --profile tests down --volumes --remove-orphans >/dev/null' EXIT; \
		docker compose -p plantguard-migrations --profile tests run --build --rm migration-test

lint:
	.venv/bin/python -m ruff check services tests scripts
	npm run lint --workspace @plantguard/web

build:
	npm run build --workspace @plantguard/web

up:
	docker compose up --build

down:
	docker compose down

db-upgrade:
	docker compose run --build --rm api alembic -c /workspace/services/api/alembic.ini upgrade head

db-downgrade:
	docker compose run --build --rm api alembic -c /workspace/services/api/alembic.ini downgrade -1

ksql-init:
	docker compose --profile tools run --rm ksqldb-init

smoke:
	python3 scripts/check_stack.py
