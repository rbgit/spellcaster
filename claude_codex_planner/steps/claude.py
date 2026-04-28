"""Steps that call the Anthropic API (Claude) for analysis and prompt generation."""

from __future__ import annotations

import json

import anthropic
from dbos import DBOS

from claude_codex_planner.config import get_anthropic_api_key, get_claude_model
from claude_codex_planner.models import (
    ContinuationDecision,
    InitialAnalysis,
    SynthesisReport,
    Turn,
)
from claude_codex_planner.prompts import (
    INITIAL_ANALYSIS_SYSTEM,
    ROUND_2_CHALLENGE_SYSTEM,
    ROUND_3_TRADEOFFS_SYSTEM,
    ROUND_4_RESOURCE_REALITY_SYSTEM,
    ROUND_5_ALTERNATIVES_SYSTEM,
    SHOULD_CONTINUE_SYSTEM,
    SYNTHESIS_SYSTEM,
)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_anthropic_api_key())


def _chat(system: str, user: str) -> str:
    """Single-turn Claude call; returns the text content of the first response block."""
    response = _client().messages.create(
        model=get_claude_model(),
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _history_to_text(history: list[Turn]) -> str:
    lines: list[str] = []
    for turn in history:
        lines.append(f"[Round {turn.round_num} — {turn.intent}]")
        lines.append(f"Claude prompt: {turn.claude_prompt}")
        lines.append(f"Codex response: {turn.codex_response}")
        lines.append("")
    return "\n".join(lines)


@DBOS.step()
def claude_initial_analysis(topic: str, plan_context: str) -> InitialAnalysis:
    user_msg = f"Topic: {topic}\n\nPlan:\n{plan_context}"
    raw = _chat(INITIAL_ANALYSIS_SYSTEM, user_msg)
    data = json.loads(raw)
    return InitialAnalysis.model_validate(data)


@DBOS.step()
def claude_round_2_challenge(history: list[Turn], initial_analysis: InitialAnalysis) -> str:
    analysis_summary = (
        f"Initial risks identified: "
        + ", ".join(
            f"{r.severity}: {r.description}" for r in initial_analysis.technical_risks
        )
    )
    user_msg = (
        f"{analysis_summary}\n\nDialogue so far:\n{_history_to_text(history)}\n\n"
        "Generate Round 2 challenge prompt for Codex."
    )
    return _chat(ROUND_2_CHALLENGE_SYSTEM, user_msg)


@DBOS.step()
def claude_round_3_tradeoffs(history: list[Turn]) -> str:
    user_msg = (
        f"Dialogue so far:\n{_history_to_text(history)}\n\n"
        "Generate Round 3 tradeoffs prompt for Codex."
    )
    return _chat(ROUND_3_TRADEOFFS_SYSTEM, user_msg)


@DBOS.step()
def claude_round_4_resource_reality(history: list[Turn]) -> str:
    user_msg = (
        f"Dialogue so far:\n{_history_to_text(history)}\n\n"
        "Generate Round 4 resource reality prompt for Codex."
    )
    return _chat(ROUND_4_RESOURCE_REALITY_SYSTEM, user_msg)


@DBOS.step()
def claude_round_5_alternatives(history: list[Turn]) -> str:
    user_msg = (
        f"Dialogue so far:\n{_history_to_text(history)}\n\n"
        "Generate Round 5 alternatives prompt for Codex."
    )
    return _chat(ROUND_5_ALTERNATIVES_SYSTEM, user_msg)


@DBOS.step()
def claude_should_continue(history: list[Turn]) -> ContinuationDecision:
    user_msg = (
        f"Dialogue so far:\n{_history_to_text(history)}\n\n"
        "Should the dialogue continue for another round?"
    )
    raw = _chat(SHOULD_CONTINUE_SYSTEM, user_msg)
    data = json.loads(raw)
    return ContinuationDecision.model_validate(data)


@DBOS.step()
def claude_synthesize(
    topic: str,
    plan_context: str,
    history: list[Turn],
    initial_analysis: InitialAnalysis,
) -> SynthesisReport:
    analysis_summary = (
        "Initial analysis:\n"
        f"Key assumptions: {initial_analysis.key_assumptions}\n"
        f"Technical risks: {[f'{r.severity}: {r.description}' for r in initial_analysis.technical_risks]}\n"
        f"Architectural concerns: {initial_analysis.architectural_concerns}\n"
        f"Operational concerns: {initial_analysis.operational_concerns}"
    )
    user_msg = (
        f"Topic: {topic}\n\nOriginal plan:\n{plan_context}\n\n"
        f"{analysis_summary}\n\n"
        f"Full dialogue:\n{_history_to_text(history)}\n\n"
        "Synthesize this into a final structured report."
    )
    raw = _chat(SYNTHESIS_SYSTEM, user_msg)
    data = json.loads(raw)
    return SynthesisReport.model_validate(data)
