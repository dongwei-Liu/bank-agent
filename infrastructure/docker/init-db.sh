#!/usr/bin/env bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  --set=app_password="$FINERACT_DB_PASSWORD" <<'SQL'
CREATE ROLE fineract LOGIN PASSWORD :'app_password';
CREATE DATABASE fineract_tenants OWNER fineract ENCODING 'UTF8';
CREATE DATABASE fineract_default OWNER fineract ENCODING 'UTF8';
SQL
