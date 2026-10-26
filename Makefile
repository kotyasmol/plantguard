.PHONY: bootstrap test test-python test-web lint build up down ksql-init smoke

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

lint:
	.venv/bin/python -m ruff check services tests scripts
	npm run lint --workspace @plantguard/web

build:
	npm run build --workspace @plantguard/web

up:
	docker compose up --build

down:
	docker compose down

ksql-init:
	docker compose --profile tools run --rm ksqldb-init

smoke:
	python3 scripts/check_stack.py
