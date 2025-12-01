#!/usr/bin/env bash
set -euo pipefail

# If a .env file exists in the project root, export its variables for the process
if [ -f "/app/.env" ]; then
  echo "Loading /app/.env"
  # shellcheck disable=SC2086
  # Export each non-comment line of .env (KEY=VALUE). This is a simple
  # approach; do not store secrets in repo if you use this.
  export $(grep -v '^#' /app/.env | xargs)
fi

exec "$@"
