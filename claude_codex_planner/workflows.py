"""Top-level durable workflow for the claude-codex-planner."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, cast

from dbos import DBOS

from claude_codex_planner.models import InitialAnalysis, SynthesisReport, Turn
from claude_codex_planner.prompts import ROUND_INTENTS
from claude_codex_planner.steps.claude import (
    claude_initial_analysis,
    claude_round_2_challenge,
    claude_round_3_tradeoffs,
    claude_round_4_resource_reality,
    claude_round_5_alternatives,
    claude_should_continue,
    claude_synthesize,
)
from claude_codex_planner.steps.codex import (
    codex_initial_assessment,
    codex_query,
    discover_codex_model,
    validate_codex_available,
)

_TurnIntent = Literal["initial", "challenge", "tradeoffs", "resource_reality", "alternatives"]


@DBOS.step()
def _get_utc_now() -> datetime:
    """Isolated step so datetime.now() is outside the workflow body."""
    return datetime.now(tz=timezone.utc)


@DBOS.workflow()
def run_planning_session(
    topic: str,
    plan_context: str,
    max_rounds: int = 5,
) -> SynthesisReport:
    """Crash-resumable multi-round dialogue workflow.

    Every external interaction (subprocess, API, I/O) is in a @DBOS.step().
    The workflow body is pure orchestration: deterministic loop + state accumulation.
    """
    # Phase 0: validate Codex is available — abort with typed error if missing.
    validate_codex_available()

    # Phase 0.5: discover model (reads env var; no network call).
    codex_model = discover_codex_model()

    # Phase 1: Claude analyses the plan and produces the opening question.
    initial_analysis: InitialAnalysis = claude_initial_analysis(topic, plan_context)

    # Phase 2: first Codex turn seeded by Claude's opening question.
    first_codex_response: str = codex_initial_assessment(
        initial_analysis.opening_question_for_codex,
        codex_model,
    )

    timestamp_r1: datetime = _get_utc_now()
    history: list[Turn] = [
        Turn(
            round_num=1,
            intent="initial",
            claude_prompt=initial_analysis.opening_question_for_codex,
            codex_response=first_codex_response,
            timestamp=timestamp_r1,
        )
    ]

    # Phases 3-N: iterative dialogue.
    for round_num in range(2, max_rounds + 1):
        intent = cast(_TurnIntent, ROUND_INTENTS.get(round_num, "alternatives"))

        # Select the correct Claude step for this round.
        if round_num == 2:
            claude_prompt: str = claude_round_2_challenge(history, initial_analysis)
        elif round_num == 3:
            claude_prompt = claude_round_3_tradeoffs(history)
        elif round_num == 4:
            claude_prompt = claude_round_4_resource_reality(history)
        else:
            claude_prompt = claude_round_5_alternatives(history)

        codex_response: str = codex_query(claude_prompt, codex_model)

        ts: datetime = _get_utc_now()
        history.append(
            Turn(
                round_num=round_num,
                intent=intent,
                claude_prompt=claude_prompt,
                codex_response=codex_response,
                timestamp=ts,
            )
        )

        # Early exit if the dialogue has reached natural resolution.
        continuation = claude_should_continue(history)
        if not continuation.should_continue:
            break

    # Final synthesis.
    report: SynthesisReport = claude_synthesize(
        topic, plan_context, history, initial_analysis
    )
    return report
