"""DBOS initialization and CLI entrypoint for claude-codex-planner."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import click
from dbos import DBOS, DBOSConfig, SetWorkflowID

from claude_codex_planner.config import get_database_url
from claude_codex_planner.models import SynthesisReport
from claude_codex_planner.steps.codex import CodexUnavailableError

# Import all DBOS-decorated modules so the decorator registry is populated before launch.
import claude_codex_planner.steps.claude  # noqa: F401
import claude_codex_planner.steps.codex  # noqa: F401
import claude_codex_planner.workflows  # noqa: F401
from claude_codex_planner.workflows import run_planning_session


def _init_dbos() -> None:
    db_url = get_database_url()
    config: DBOSConfig = {
        "name": "claude-codex-planner",
        "system_database_url": db_url,
    }
    DBOS(config=config)
    DBOS.launch()


def _render_report(report: SynthesisReport) -> str:
    """Render a SynthesisReport as markdown matching the original spec template."""
    lines: list[str] = []

    lines.append("## EXECUTIVE SUMMARY")
    lines.append(report.executive_summary)
    lines.append("")

    lines.append("## ORIGINAL PLAN/QUESTION")
    lines.append(report.original_plan_restatement)
    lines.append("")

    lines.append("## CLAUDE-CODEX DIALOGUE HIGHLIGHTS")
    lines.append("### Key Insights from Discussion")
    for item in report.dialogue_highlights:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### Areas of Agreement")
    for item in report.areas_of_agreement:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### Points of Constructive Disagreement")
    for item in report.points_of_constructive_disagreement:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## CONSENSUS ANALYSIS")
    lines.append("")
    lines.append("### Merits (Validated Strengths)")
    for item in report.consensus_analysis.validated_strengths:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### Demerits & Risks")
    for risk in report.consensus_analysis.confirmed_risks:
        lines.append(f"- [{risk.severity}] {risk.description}")
    lines.append("")

    lines.append("### Points of Disagreement")
    for item in report.consensus_analysis.points_of_disagreement:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## REFINED RECOMMENDATIONS")
    lines.append("")
    lines.append("### Primary Recommendation")
    lines.append(report.refined_recommendations.primary_recommendation)
    lines.append("")

    if report.refined_recommendations.alternative_approaches:
        lines.append("### Alternative Approaches")
        for item in report.refined_recommendations.alternative_approaches:
            lines.append(f"- {item}")
        lines.append("")

    if report.refined_recommendations.conditional_guidance:
        lines.append("### Conditional Guidance")
        for item in report.refined_recommendations.conditional_guidance:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("## IMPLEMENTATION CONSIDERATIONS")
    lines.append("")
    lines.append("### Resource Requirements")
    for item in report.implementation_considerations.resource_requirements:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### Timeline Estimates")
    lines.append(report.implementation_considerations.timeline_estimate)
    lines.append("")

    lines.append("### Risk Mitigation Strategies")
    for item in report.implementation_considerations.risk_mitigations:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### Next Steps")
    for i, step in enumerate(report.implementation_considerations.next_steps, 1):
        lines.append(f"{i}. {step}")

    return "\n".join(lines)


@click.command()
@click.argument("topic")
@click.option(
    "--context-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to a file containing the plan context.",
)
@click.option("--context", "context_text", default="", help="Inline plan context string.")
@click.option("--max-rounds", default=5, show_default=True, help="Maximum dialogue rounds.")
@click.option(
    "--workflow-id",
    default=None,
    help="Explicit workflow ID for resume-after-crash.",
)
def cli(
    topic: str,
    context_file: Path | None,
    context_text: str,
    max_rounds: int,
    workflow_id: str | None,
) -> None:
    """Run a collaborative Claude-Codex planning session.

    TOPIC is the subject being analysed (e.g. "Migrate billing to 3 services").
    """
    if context_file is not None:
        plan_context = context_file.read_text()
    elif context_text:
        plan_context = context_text
    else:
        click.echo("Provide --context-file or --context.", err=True)
        sys.exit(1)

    _init_dbos()

    try:
        if workflow_id:
            with SetWorkflowID(workflow_id):
                report = run_planning_session(topic, plan_context, max_rounds)
        else:
            report = run_planning_session(topic, plan_context, max_rounds)

        click.echo(_render_report(report))
    except CodexUnavailableError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        click.echo(
            textwrap.dedent("""
                Codex CLI is required for this tool.
                Install: npm install -g @openai/codex
                Verify:  codex --version
                Set key: export OPENAI_API_KEY=sk-...
            """).strip(),
            err=True,
        )
        sys.exit(2)
    finally:
        DBOS.destroy()


if __name__ == "__main__":
    cli()
