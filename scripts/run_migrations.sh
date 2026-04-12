#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${DATABASE_URL:-}" ]]; then
  psql "$DATABASE_URL" -f schema.sql
  psql "$DATABASE_URL" -f migrations/002_add_extended_columns.sql
else
  : "${DB_HOST:?DB_HOST is required}"
  : "${DB_NAME:?DB_NAME is required}"
  : "${DB_USER:?DB_USER is required}"
  : "${DB_PORT:=5432}"
  psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -f schema.sql
  psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -f migrations/002_add_extended_columns.sql
fi

echo "Migrations completed successfully."
