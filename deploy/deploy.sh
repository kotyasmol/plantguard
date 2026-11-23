#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
env_file=${PLANTGUARD_ENV_FILE:-$script_dir/.env.production}
compose_file=$script_dir/compose.production.yaml

if [ ! -f "$env_file" ]; then
    echo "Production environment file not found: $env_file" >&2
    exit 1
fi

cd "$project_dir"

docker compose --env-file "$env_file" -f "$compose_file" config --quiet
docker compose --env-file "$env_file" -f "$compose_file" build api
docker compose --env-file "$env_file" -f "$compose_file" up --detach --wait
docker compose --env-file "$env_file" -f "$compose_file" --profile tools run --rm ksqldb-init
docker compose --env-file "$env_file" -f "$compose_file" exec -T api \
    python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=5)"

echo "PlantGuard deployment is healthy."
