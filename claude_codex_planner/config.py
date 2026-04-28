"""Environment variable loading for claude-codex-planner."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_anthropic_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return key


def get_openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return key


def get_codex_model() -> str:
    # TODO: replace hardcoded fallback with web search for latest model
    # (the original spec's hardcoded "5.2" was a bug; env var takes precedence)
    return os.environ.get("CODEX_MODEL", "o3")


def get_database_url() -> str:
    url = os.environ.get("DBOS_DATABASE_URL", "")
    if not url:
        raise RuntimeError("DBOS_DATABASE_URL environment variable is not set")
    return url


def get_claude_model() -> str:
    return os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")
