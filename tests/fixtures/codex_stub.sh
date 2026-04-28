#!/usr/bin/env bash
# Deterministic Codex CLI stub for testing.
# Usage: codex [-m <model>] "<prompt>"
# Echoes a fixed response keyed on prompt content so tests can assert round-specific output.

# Parse args: consume optional -m <model>, then the prompt is the last positional argument.
while [[ $# -gt 0 ]]; do
    case "$1" in
        -m)
            shift 2  # skip flag and value
            ;;
        *)
            PROMPT="$1"
            shift
            ;;
    esac
done

PROMPT_LOWER="${PROMPT,,}"

if [[ "$PROMPT_LOWER" == *"merits"* ]] || [[ "$PROMPT_LOWER" == *"present this plan"* ]]; then
    echo "STUB_ROUND_1: The plan has clear technical merit. Key challenges include data migration complexity, service discovery overhead, and distributed transaction management. The microservices approach provides better scalability but introduces operational complexity."

elif [[ "$PROMPT_LOWER" == *"you said"* ]] || [[ "$PROMPT_LOWER" == *"but what about"* ]] || [[ "$PROMPT_LOWER" == *"counter"* ]]; then
    echo "STUB_ROUND_2: Fair challenge. I acknowledge that distributed transaction management is harder than I initially suggested. Two-phase commit adds significant latency (50-200ms per operation) and failure recovery is non-trivial. The optimistic complexity estimate was incorrect — saga pattern alone requires 3-4 weeks of careful design."

elif [[ "$PROMPT_LOWER" == *"rank"* ]] || [[ "$PROMPT_LOWER" == *"tradeoff"* ]] || [[ "$PROMPT_LOWER" == *"latency"* ]]; then
    echo "STUB_ROUND_3: Comparison: Approach A (full decomposition) — latency: +40ms p99, operational complexity: HIGH, blast radius: MEDIUM (isolated failures), team learning curve: 8 weeks, cost: +30% infra. Approach B (strangler fig) — latency: +5ms, operational complexity: LOW initially, blast radius: LOW, team learning: 2 weeks, cost: +5% initially."

elif [[ "$PROMPT_LOWER" == *"underestimat"* ]] || [[ "$PROMPT_LOWER" == *"person-week"* ]] || [[ "$PROMPT_LOWER" == *"bus-factor"* ]]; then
    echo "STUB_ROUND_4: Timeline reality: Phase 1 (extraction): 8 person-weeks not 4. Phase 2 (data migration): 12 person-weeks not 6. Phase 3 (cutover): 4 person-weeks. Total: 24 person-weeks minimum. Bus-factor risk is HIGH — 2 engineers own the domain model. If either leaves, add 6 weeks for knowledge transfer."

elif [[ "$PROMPT_LOWER" == *"monolith"* ]] || [[ "$PROMPT_LOWER" == *"strangler"* ]] || [[ "$PROMPT_LOWER" == *"alternative"* ]] || [[ "$PROMPT_LOWER" == *"opposite"* ]]; then
    echo "STUB_ROUND_5: Strangler fig is genuinely competitive. Extract billing as a single bounded context first: 12 person-weeks vs 24, lower risk, immediate value. Only proceed to 3-service split if billing alone proves the pattern. The original plan skipped the intermediate step which is where most migrations fail."

else
    echo "STUB_DEFAULT: I have analysed the technical aspects. The approach has merit but requires careful consideration of the failure modes, operational overhead, and team capacity constraints discussed in this dialogue."
fi

exit 0
