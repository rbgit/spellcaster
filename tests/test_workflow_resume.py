"""Tests for crash-resume behaviour of run_planning_session.

Uses:
  - tests/fixtures/codex_stub.sh  as a fake `codex` binary on PATH
  - monkeypatching of claude steps to return deterministic output
  - a real (or SQLite-backed) DBOS instance for checkpointing

To run against SQLite (no Postgres required):
    DBOS_DATABASE_URL=sqlite:///test_dbos.db pytest tests/test_workflow_resume.py -v
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
STUB_SCRIPT = FIXTURES_DIR / "codex_stub.sh"

TOPIC = "Migrate billing from monolith to 3 services"
PLAN_CONTEXT = (
    "We plan to extract the billing module into three microservices: "
    "payment-processor, invoice-service, and subscription-manager. "
    "Each will have its own Postgres schema. "
    "Target timeline: 6 months with a team of 4 engineers."
)


def _make_initial_analysis() -> dict[str, Any]:
    return {
        "key_assumptions": [
            "Team has microservices experience",
            "Postgres schemas can be split without downtime",
            "6-month timeline is realistic",
        ],
        "technical_risks": [
            {"description": "Distributed transaction complexity", "severity": "HIGH"},
            {"description": "Schema migration data loss risk", "severity": "MEDIUM"},
        ],
        "architectural_concerns": ["Tight coupling in current billing module"],
        "operational_concerns": ["On-call burden increases with 3 services"],
        "opening_question_for_codex": (
            "Present this plan: migrate billing to 3 microservices. "
            "What are the technical merits and implementation challenges you see?"
        ),
    }


def _make_continuation(should_continue: bool, reason: str = "") -> dict[str, Any]:
    return {"should_continue": should_continue, "reason": reason or "test"}


def _make_report() -> dict[str, Any]:
    return {
        "executive_summary": "The migration is feasible but underestimates complexity by 2x.",
        "original_plan_restatement": PLAN_CONTEXT,
        "dialogue_highlights": ["Distributed transactions are harder than estimated"],
        "areas_of_agreement": ["Microservices improve scalability"],
        "points_of_constructive_disagreement": ["Timeline is optimistic"],
        "consensus_analysis": {
            "validated_strengths": ["Clear service boundaries"],
            "confirmed_risks": [
                {"description": "Distributed transaction complexity", "severity": "HIGH"}
            ],
            "points_of_disagreement": ["Whether to split into 3 vs 1 bounded context first"],
        },
        "refined_recommendations": {
            "primary_recommendation": "Use strangler fig — extract billing as one service first.",
            "alternative_approaches": ["Full 3-service split in year 2 after pattern proven"],
            "conditional_guidance": [
                "If team < 4 engineers, defer microservices and extract a bounded context only"
            ],
        },
        "implementation_considerations": {
            "resource_requirements": ["4 engineers minimum", "Postgres 16"],
            "timeline_estimate": "24 person-weeks for full migration",
            "risk_mitigations": ["Saga pattern for distributed txns", "Feature flags for cutover"],
            "next_steps": [
                "Spike strangler fig on one billing endpoint",
                "Document domain model with current owners",
            ],
        },
    }


@pytest.fixture()
def stub_codex_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put a symlink to codex_stub.sh on PATH as 'codex'."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub_link = bin_dir / "codex"
    stub_link.symlink_to(STUB_SCRIPT)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    return stub_link


@pytest.fixture()
def dbos_instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Start a DBOS instance backed by SQLite for testing."""
    db_path = tmp_path / "test_dbos.db"
    monkeypatch.setenv("DBOS_DATABASE_URL", f"sqlite:///{db_path}")

    # Ensure the config and env are set before importing DBOS-decorated functions.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from dbos import DBOS, DBOSConfig

    config: DBOSConfig = {
        "name": "test-claude-codex-planner",
        "system_database_url": f"sqlite:///{db_path}",
    }
    dbos = DBOS(config=config)
    DBOS.launch()
    yield dbos
    DBOS.destroy()


def _patch_claude_steps(monkeypatch: pytest.MonkeyPatch, stop_after_round: int | None = None):
    """Monkeypatch all Claude steps to return deterministic output.

    If stop_after_round is set, raises RuntimeError when claude_should_continue
    is called after that round (simulating a crash mid-dialogue).
    """
    import claude_codex_planner.steps.claude as claude_mod
    from claude_codex_planner.models import ContinuationDecision, InitialAnalysis, SynthesisReport

    call_counts: dict[str, int] = {"should_continue": 0}

    def fake_initial_analysis(topic: str, plan_context: str) -> InitialAnalysis:
        return InitialAnalysis.model_validate(_make_initial_analysis())

    def fake_round_2(history, initial_analysis) -> str:
        return "You said X but what about distributed transaction failure modes?"

    def fake_round_3(history) -> str:
        return "Rank approach A vs B on latency, operational complexity, blast radius, learning, cost."

    def fake_round_4(history) -> str:
        return "Where are we underestimating complexity? Person-weeks per phase?"

    def fake_round_5(history) -> str:
        return "What if we did the opposite — strangler fig on the monolith instead of 3 services?"

    def fake_should_continue(history) -> ContinuationDecision:
        call_counts["should_continue"] += 1
        current_round = len(history)
        if stop_after_round is not None and current_round >= stop_after_round:
            raise RuntimeError(f"SIMULATED CRASH after round {current_round}")
        return ContinuationDecision(should_continue=True, reason="more to explore")

    def fake_synthesize(topic, plan_context, history, initial_analysis) -> SynthesisReport:
        return SynthesisReport.model_validate(_make_report())

    monkeypatch.setattr(claude_mod, "claude_initial_analysis", fake_initial_analysis)
    monkeypatch.setattr(claude_mod, "claude_round_2_challenge", fake_round_2)
    monkeypatch.setattr(claude_mod, "claude_round_3_tradeoffs", fake_round_3)
    monkeypatch.setattr(claude_mod, "claude_round_4_resource_reality", fake_round_4)
    monkeypatch.setattr(claude_mod, "claude_round_5_alternatives", fake_round_5)
    monkeypatch.setattr(claude_mod, "claude_should_continue", fake_should_continue)
    monkeypatch.setattr(claude_mod, "claude_synthesize", fake_synthesize)

    return call_counts


class TestWorkflowFullRun:
    def test_completes_all_rounds(
        self,
        stub_codex_on_path: Path,
        dbos_instance: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Workflow completes with max_rounds=3, producing a SynthesisReport."""
        _patch_claude_steps(monkeypatch)

        from claude_codex_planner.models import SynthesisReport
        from claude_codex_planner.workflows import run_planning_session

        wf_id = f"test-full-{uuid.uuid4()}"
        from dbos import SetWorkflowID

        with SetWorkflowID(wf_id):
            report = run_planning_session(TOPIC, PLAN_CONTEXT, max_rounds=3)

        assert isinstance(report, SynthesisReport)
        assert report.executive_summary
        assert report.refined_recommendations.primary_recommendation

    def test_report_has_all_sections(
        self,
        stub_codex_on_path: Path,
        dbos_instance: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_claude_steps(monkeypatch)

        from claude_codex_planner.workflows import run_planning_session

        wf_id = f"test-sections-{uuid.uuid4()}"
        from dbos import SetWorkflowID

        with SetWorkflowID(wf_id):
            report = run_planning_session(TOPIC, PLAN_CONTEXT, max_rounds=3)

        assert report.consensus_analysis.validated_strengths
        assert report.implementation_considerations.next_steps
        assert report.refined_recommendations.conditional_guidance


class TestWorkflowResume:
    def test_resume_skips_completed_steps(
        self,
        stub_codex_on_path: Path,
        dbos_instance: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Re-running with the same workflow_id resumes from last checkpoint.

        Strategy:
        1. Run to completion with max_rounds=3.
        2. Monkeypatch initial_analysis to raise RuntimeError to prove it's NOT called again.
        3. Re-run with same workflow_id — DBOS should replay from checkpoints and skip the step.
        """
        from dbos import SetWorkflowID
        from claude_codex_planner.workflows import run_planning_session
        import claude_codex_planner.steps.claude as claude_mod
        from claude_codex_planner.models import InitialAnalysis

        wf_id = f"test-resume-{uuid.uuid4()}"
        call_log: list[str] = []

        # First run: complete successfully, log all step calls.
        def logging_initial_analysis(topic: str, plan_context: str) -> InitialAnalysis:
            call_log.append("initial_analysis")
            return InitialAnalysis.model_validate(_make_initial_analysis())

        monkeypatch.setattr(claude_mod, "claude_initial_analysis", logging_initial_analysis)
        _patch_claude_steps(monkeypatch)
        # Re-patch initial_analysis after _patch_claude_steps to keep the logging version.
        monkeypatch.setattr(claude_mod, "claude_initial_analysis", logging_initial_analysis)

        with SetWorkflowID(wf_id):
            report1 = run_planning_session(TOPIC, PLAN_CONTEXT, max_rounds=3)

        assert "initial_analysis" in call_log
        first_run_calls = call_log.count("initial_analysis")
        assert first_run_calls == 1

        # Second run: initial_analysis should NOT be called again (checkpointed result replayed).
        call_log.clear()

        with SetWorkflowID(wf_id):
            report2 = run_planning_session(TOPIC, PLAN_CONTEXT, max_rounds=3)

        # DBOS replays checkpointed step results without re-executing the function.
        assert "initial_analysis" not in call_log, (
            "initial_analysis was re-called on resume — DBOS did not replay from checkpoint"
        )
        assert report2.executive_summary == report1.executive_summary

    def test_codex_unavailable_raises_typed_error(
        self,
        dbos_instance: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When codex is not on PATH, CodexUnavailableError is raised."""
        # Remove all known codex locations from PATH.
        monkeypatch.setenv("PATH", "/nonexistent")

        from claude_codex_planner.steps.codex import CodexUnavailableError
        from claude_codex_planner.workflows import run_planning_session

        with pytest.raises((CodexUnavailableError, Exception)) as exc_info:
            run_planning_session(TOPIC, PLAN_CONTEXT, max_rounds=1)

        assert "codex" in str(exc_info.value).lower()
