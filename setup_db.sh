#!/usr/bin/env sh
psql -U postgres <<SQL
CREATE USER dbos WITH PASSWORD 'dbos';
CREATE DATABASE claude_codex_planner OWNER dbos;
SQL
