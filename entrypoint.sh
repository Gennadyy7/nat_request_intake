#!/bin/sh
set -e

AGGREGATED_DIR="${SPIN_AGGREGATED_BASE_DIR:-/app/data/aggregated}"

mkdir -p "$AGGREGATED_DIR"
chown -R appuser:appuser "$AGGREGATED_DIR"

echo "Applying migrations..."
gosu appuser alembic upgrade head || {
  echo "Migrations failed. Exiting..."
  exit 1
}

echo "Starting app..."
exec gosu appuser python -m app.main
