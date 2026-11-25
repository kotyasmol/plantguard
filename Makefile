.PHONY: bootstrap dataset-audit train-species-model evaluate-visual-model evaluate-text-model evaluate-comparison-model test test-python test-web test-coverage test-migrations test-streams lint build up down db-upgrade db-downgrade ksql-init smoke

bootstrap:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements-dev.txt
	npm install

dataset-audit:
	.venv/bin/python scripts/dataset_registry.py \
		--manifest datasets/plantguard-v1/manifest.jsonl \
		--report datasets/plantguard-v1/audit-report.json

train-species-model:
	.venv/bin/python scripts/train_species_identifier.py

evaluate-visual-model:
	.venv/bin/python scripts/evaluate_visual_baseline.py

evaluate-text-model:
	.venv/bin/python scripts/evaluate_text_baseline.py

evaluate-comparison-model:
	.venv/bin/python scripts/evaluate_comparison_baseline.py

test: test-python test-web

test-python:
	.venv/bin/python -m pytest

test-web:
	npm run test --workspace @plantguard/web

test-coverage:
	.venv/bin/python -m pytest --cov=plantguard_api --cov=plantguard_mining --cov-report=term-missing --cov-fail-under=85
	npm run test:coverage --workspace @plantguard/web

test-migrations:
	@trap 'docker compose -p plantguard-migrations --profile tests down --volumes --remove-orphans >/dev/null' EXIT; \
		docker compose -p plantguard-migrations --profile tests run --build --rm migration-test

test-streams:
	@set -eu; \
		compose='docker compose -p plantguard-streams -f compose.yaml -f deploy/compose.test-streams.yaml'; \
		trap "$$compose down --volumes --remove-orphans >/dev/null" EXIT; \
		$$compose up --detach --wait kafka ksqldb; \
		$$compose --profile tools run --rm ksqldb-init; \
		$$compose run --build --rm --no-deps api \
			python /workspace/scripts/test_stream_processing.py

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
