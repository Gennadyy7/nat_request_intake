#!/bin/sh
set -e

if [ -z "${SPIN_AGGREGATED_BASE_DIR}" ]; then
  echo "SPIN_AGGREGATED_BASE_DIR is not set. Exiting..." >&2
  exit 1
fi

mkdir -p "$SPIN_AGGREGATED_BASE_DIR"
chown -R appuser:appuser "$SPIN_AGGREGATED_BASE_DIR"

echo "Applying migrations..."
gosu appuser alembic upgrade head || {
  echo "Migrations failed. Exiting..."
  exit 1
}

echo "Starting app..."
exec gosu appuser python -m app.main
