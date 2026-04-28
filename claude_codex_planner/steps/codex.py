"""Steps that interact with Codex CLI via subprocess."""

from __future__ import annotations

import shutil
import subprocess

from dbos import DBOS

from claude_codex_planner.config import get_codex_model


class CodexError(RuntimeError):
    """Raised when Codex CLI exits with a nonzero code or times out."""

    def __init__(self, message: str, returncode: int | None = None) -> None:
        super().__init__(message)
        self.returncode = returncode


class CodexUnavailableError(RuntimeError):
    """Raised when the codex binary cannot be found on PATH."""


def _invoke_codex(prompt: str, model: str, timeout_seconds: int) -> str:
    """Raw subprocess call to codex; shared by both step wrappers."""
    try:
        result = subprocess.run(
            ["codex", "-m", model, prompt],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise CodexError(
            f"codex timed out after {timeout_seconds}s for prompt: {prompt[:80]}..."
        ) from exc

    if result.returncode != 0:
        stderr_snippet = result.stderr[:500] if result.stderr else "(no stderr)"
        raise CodexError(
            f"codex exited {result.returncode}: {stderr_snippet}",
            returncode=result.returncode,
        )

    return result.stdout.strip()


@DBOS.step()
def validate_codex_available() -> None:
    """Abort with typed error if `codex` is not on PATH."""
    if shutil.which("codex") is None:
        raise CodexUnavailableError(
            "codex binary not found on PATH. "
            "Install it with: npm install -g @openai/codex  "
            "Then verify: codex --version"
        )


@DBOS.step()
def discover_codex_model() -> str:
    """Return the Codex model to use.

    Reads CODEX_MODEL env var; falls back to 'o3'.
    TODO: add web-search-based model discovery to replace the hardcoded fallback
    (the original spec's hardcoded '5.2' was a bug).
    """
    return get_codex_model()


@DBOS.step(retries_allowed=True, max_attempts=3, interval_seconds=2.0, backoff_rate=2.0)
def codex_query(prompt: str, model: str, timeout_seconds: int = 120) -> str:
    """Send a single prompt to Codex CLI and return its stdout response."""
    return _invoke_codex(prompt, model, timeout_seconds)


@DBOS.step(retries_allowed=True, max_attempts=3, interval_seconds=2.0, backoff_rate=2.0)
def codex_initial_assessment(opening_question: str, model: str) -> str:
    """First Codex turn: send the opening question and return the response."""
    return _invoke_codex(opening_question, model, timeout_seconds=120)


if __name__ == "__main__":
    # Smoke test — requires codex on PATH and OPENAI_API_KEY set.
    import sys

    try:
        if shutil.which("codex") is None:
            print("ERROR: codex not on PATH")
            sys.exit(1)
        model = get_codex_model()
        print(f"model: {model}")
        response = _invoke_codex("Say exactly: CODEX_OK", model, timeout_seconds=60)
        print(f"codex response: {response}")
    except CodexError as exc:
        print(f"CodexError: {exc}")
        sys.exit(1)
