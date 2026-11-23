#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
env_file=${PLANTGUARD_ENV_FILE:-$script_dir/.env.production}
backup_dir=${PLANTGUARD_BACKUP_DIR:-/var/backups/plantguard}
compose_file=$script_dir/compose.production.yaml

case "$backup_dir" in
    /*) ;;
    *) echo "PLANTGUARD_BACKUP_DIR must be an absolute path" >&2; exit 1 ;;
esac
if [ "$backup_dir" = "/" ]; then
    echo "Refusing to use / as backup directory" >&2
    exit 1
fi
if [ ! -f "$env_file" ]; then
    echo "Production environment file not found: $env_file" >&2
    exit 1
fi

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
cd "$project_dir"

database_backup=$backup_dir/postgres-$timestamp.sql.gz
photo_backup=$backup_dir/photos-$timestamp.tar.gz

docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
    sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip -9 > "$database_backup"
docker compose --env-file "$env_file" -f "$compose_file" exec -T api \
    python -c 'import sys, tarfile; archive=tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz"); archive.add("/var/lib/plantguard/photos", arcname="photos"); archive.close()' \
    > "$photo_backup"

gzip -t "$database_backup"
tar -tzf "$photo_backup" >/dev/null
sha256sum "$database_backup" "$photo_backup" > "$backup_dir/checksums-$timestamp.txt"

echo "Backup created in $backup_dir at $timestamp."
