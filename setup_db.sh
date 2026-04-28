#!/usr/bin/env bash
set -euo pipefail

DB=claude_codex_planner
ROLE=dbos
PW=dbos

psql -U postgres -c "CREATE ROLE $ROLE LOGIN PASSWORD '$PW';" 2>/dev/null || true
psql -U postgres -c "CREATE DATABASE $DB OWNER $ROLE;" 2>/dev/null || true

echo "Done. Add to your environment:"
echo "  export DBOS_DATABASE_URL=postgresql://$ROLE:$PW@localhost:5432/$DB"
