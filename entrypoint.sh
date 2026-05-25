#!/bin/sh

echo "Applying migrations..."
alembic upgrade head || {
  echo "Migrations failed. Exiting..."
  exit 1
}

echo "Starting app..."
exec python -m app.main