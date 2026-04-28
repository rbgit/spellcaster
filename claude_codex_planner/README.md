# claude-codex-planner

A crash-resumable DBOS Python application that orchestrates a multi-turn dialogue between Claude (analyst) and Codex CLI (peer) to collaboratively stress-test technical plans, then synthesises a structured report.

Every round of dialogue is checkpointed in Postgres. If the process crashes mid-dialogue, re-running with the same `--workflow-id` resumes from the last completed step without re-calling earlier steps or re-billing API calls.

---

## Architecture

```
run_planning_session (workflow)
├── validate_codex_available   (step — shutil.which)
├── discover_codex_model       (step — env var read)
├── claude_initial_analysis    (step — Anthropic API → InitialAnalysis)
├── codex_initial_assessment   (step — subprocess → str)
└── loop rounds 2-N:
    ├── claude_round_N_*       (step — Anthropic API → str prompt)
    ├── codex_query            (step — subprocess, retries=3 → str)
    ├── _get_utc_now           (step — datetime isolation → datetime)
    └── claude_should_continue (step — Anthropic API → ContinuationDecision)
└── claude_synthesize          (step — Anthropic API → SynthesisReport)
```

Every box labelled `step` is a `@DBOS.step()` — its return value is serialised to Postgres before the next step begins. The workflow body is pure orchestration: no I/O, no subprocess, no API calls, no `datetime.now()`.

---

## Requirements

- Python 3.11+
- Node.js 18+ (for Codex CLI)
- Docker + Docker Compose (for Postgres 16)
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

---

## Install

```bash
# From the spellcaster repo root:
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Start Postgres

```bash
docker-compose up -d
# Confirm healthy:
docker-compose ps
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | — | Anthropic API key |
| `OPENAI_API_KEY` | yes | — | OpenAI API key (used by Codex CLI) |
| `CODEX_MODEL` | no | `o3` | Codex model name |
| `DBOS_DATABASE_URL` | yes | — | Postgres connection URL |
| `CLAUDE_MODEL` | no | `claude-opus-4-7` | Claude model for analyst steps |

Create a `.env` file at the repo root:

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DBOS_DATABASE_URL=postgresql://dbos:dbos@localhost:5432/claude_codex_planner
CODEX_MODEL=o3
```

---

## Install Codex CLI

```bash
npm install -g @openai/codex
codex --version   # verify
```

---

## Run a Planning Session

```bash
# With a plan file:
python -m claude_codex_planner \
  "Migrate billing from monolith to 3 services" \
  --context-file plan.md \
  --max-rounds 5 \
  --workflow-id billing-migration-001

# With an inline context string:
python -m claude_codex_planner \
  "Migrate billing from monolith to 3 services" \
  --context "We plan to extract billing into payment-processor, invoice-service, and subscription-manager with separate Postgres schemas." \
  --max-rounds 5 \
  --workflow-id billing-migration-001
```

Output is a markdown report printed to stdout.

---

## Crash-and-Resume Demo

```bash
# 1. Start a session:
python -m claude_codex_planner "Migrate billing" \
  --context-file plan.md --workflow-id demo-001

# 2. Kill it mid-dialogue (e.g. Ctrl-C after round 2 completes).

# 3. Re-run with the same --workflow-id:
python -m claude_codex_planner "Migrate billing" \
  --context-file plan.md --workflow-id demo-001

# DBOS replays rounds 1-2 outputs from Postgres without re-calling any APIs.
# The session continues from round 3 forward.
```

---

## Inspect Checkpointed State in Postgres

```sql
-- Connect:
psql $DBOS_DATABASE_URL

-- Workflow status:
SELECT workflow_uuid, status, name, created_at, updated_at
FROM dbos.workflow_status
ORDER BY created_at DESC LIMIT 10;

-- Step outputs (serialised return values of each @DBOS.step()):
SELECT workflow_uuid, function_name, output, created_at
FROM dbos.operation_outputs
WHERE workflow_uuid = 'demo-001'
ORDER BY created_at;
```

---

## Run Tests

Tests use a SQLite-backed DBOS instance — no Postgres required:

```bash
pytest tests/test_workflow_resume.py -v
```

The test suite:
1. Runs the workflow to completion using `tests/fixtures/codex_stub.sh` (deterministic Codex fake) and monkeypatched Claude steps.
2. Re-runs with the same workflow ID and asserts `claude_initial_analysis` is **not** re-called — DBOS replays from checkpoint.
3. Asserts a missing `codex` binary raises `CodexUnavailableError`.

---

## Example Report

Output of a smoke test run with `tests/fixtures/codex_stub.sh` as the Codex fake:

```markdown
## EXECUTIVE SUMMARY
The migration is feasible but underestimates complexity by approximately 2x. A strangler-fig
approach — extracting billing as a single bounded context before splitting into three services —
reduces risk significantly and should be the first milestone.

## ORIGINAL PLAN/QUESTION
Extract the billing module into three microservices: payment-processor, invoice-service,
and subscription-manager. Each will have its own Postgres schema. Target timeline: 6 months
with a team of 4 engineers.

## CLAUDE-CODEX DIALOGUE HIGHLIGHTS
### Key Insights from Discussion
- Distributed transaction management is harder than initially acknowledged: saga pattern alone
  requires 3-4 weeks of careful design
- Actual timeline is 24 person-weeks minimum, not the estimated 12
- The intermediate step (single billing service first) has been skipped — this is where most
  migrations fail
- Bus-factor risk is HIGH: 2 engineers own the domain model

### Areas of Agreement
- Microservices provide better scalability at scale
- Clear service boundaries are achievable within the billing domain
- Feature flags are essential for safe cutover

### Points of Constructive Disagreement
- Full 3-service split immediately vs. extracting one bounded context first
- Whether the team learning curve justifies the full decomposition in the initial milestone

## CONSENSUS ANALYSIS

### Merits (Validated Strengths)
- Clear service boundaries exist in the billing domain
- Postgres schema separation is achievable without full data migration upfront

### Demerits & Risks
- [HIGH] Distributed transaction complexity: saga pattern underestimated
- [HIGH] Bus-factor: 2 engineers own critical domain knowledge
- [MEDIUM] Timeline optimism: 12 person-weeks estimated, 24 realistic

### Points of Disagreement
- Full 3-service split vs. strangler-fig to single billing service first

## REFINED RECOMMENDATIONS

### Primary Recommendation
Extract billing as a single bounded context (strangler fig) first. Prove the pattern over 12
person-weeks before splitting into 3 services. Only proceed to the full decomposition if the
first extraction succeeds within budget and timeline.

### Alternative Approaches
- Full 3-service split in year 2 after the pattern is proven on the single extraction
- Keep the monolith and add read replicas if the primary concern is read scalability

### Conditional Guidance
- If team < 4 engineers, defer microservices and extract a single bounded context only
- If distributed transaction design exceeds 6 weeks, consolidate payment-processor and
  invoice-service into one service
- If a key domain engineer leaves, pause migration and document the domain model first

## IMPLEMENTATION CONSIDERATIONS

### Resource Requirements
- 4 engineers minimum (2 senior, 2 mid-level)
- Postgres 16 with logical replication enabled
- Service mesh or API gateway for service discovery

### Timeline Estimates
Phase 1 (strangler fig extraction): 12 person-weeks.
Phase 2 (schema migration and cutover): 8 person-weeks.
Phase 3 (3-service split, if pursued): 12 additional person-weeks.
Total to strangler fig completion: ~20 person-weeks.

### Risk Mitigation Strategies
- Saga pattern for distributed transactions (design spike in week 1)
- Feature flags for all cutover points
- Dual-write period of minimum 2 sprints before hard cutover
- Document domain model with current 2 owners before any extraction begins

### Next Steps
1. Spike strangler fig pattern on one billing endpoint (1 week)
2. Document domain model with current owners (1 week, non-negotiable before any migration)
3. Decision checkpoint: proceed to Phase 1 based on spike results
4. Define saga compensation logic for payment-processor failure scenarios
```
