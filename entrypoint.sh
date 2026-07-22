#!/bin/sh
set -e

# Container mount paths must match these env values (see docker-compose.yml volumes).

if [ -z "${SPIN_AGGREGATED_BASE_DIR}" ]; then
  echo "SPIN_AGGREGATED_BASE_DIR is not set. Exiting..." >&2
  exit 1
fi
case "$SPIN_AGGREGATED_BASE_DIR" in
  /*) ;;
  *)
    echo "SPIN_AGGREGATED_BASE_DIR must be an absolute path. Exiting..." >&2
    exit 1
    ;;
esac

if [ -z "${NAT_UPLOAD_BASE_DIR}" ]; then
  echo "NAT_UPLOAD_BASE_DIR is not set. Exiting..." >&2
  exit 1
fi
case "$NAT_UPLOAD_BASE_DIR" in
  /*) ;;
  *)
    echo "NAT_UPLOAD_BASE_DIR must be an absolute path. Exiting..." >&2
    exit 1
    ;;
esac

mkdir -p "$SPIN_AGGREGATED_BASE_DIR"
chown -R appuser:appuser "$SPIN_AGGREGATED_BASE_DIR"

mkdir -p "$NAT_UPLOAD_BASE_DIR"
chown -R appuser:appuser "$NAT_UPLOAD_BASE_DIR"

echo "Applying migrations..."
gosu appuser alembic upgrade head || {
  echo "Migrations failed. Exiting..."
  exit 1
}

echo "Starting app..."
exec gosu appuser python -m app.main
