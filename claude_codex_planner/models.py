from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TechnicalRisk(BaseModel):
    description: str
    severity: Literal["HIGH", "MEDIUM", "LOW"]


class InitialAnalysis(BaseModel):
    key_assumptions: list[str]
    technical_risks: list[TechnicalRisk]
    architectural_concerns: list[str]
    operational_concerns: list[str]
    opening_question_for_codex: str


class Turn(BaseModel):
    round_num: int
    intent: Literal["initial", "challenge", "tradeoffs", "resource_reality", "alternatives"]
    claude_prompt: str
    codex_response: str
    timestamp: datetime


class ContinuationDecision(BaseModel):
    should_continue: bool
    reason: str


class ConsensusAnalysis(BaseModel):
    validated_strengths: list[str]
    confirmed_risks: list[TechnicalRisk]
    points_of_disagreement: list[str]


class RefinedRecommendations(BaseModel):
    primary_recommendation: str
    alternative_approaches: list[str]
    conditional_guidance: list[str]


class ImplementationConsiderations(BaseModel):
    resource_requirements: list[str]
    timeline_estimate: str
    risk_mitigations: list[str]
    next_steps: list[str]


class SynthesisReport(BaseModel):
    executive_summary: str
    original_plan_restatement: str
    dialogue_highlights: list[str]
    areas_of_agreement: list[str]
    points_of_constructive_disagreement: list[str]
    consensus_analysis: ConsensusAnalysis
    refined_recommendations: RefinedRecommendations
    implementation_considerations: ImplementationConsiderations
