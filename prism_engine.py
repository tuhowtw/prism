"""
Prism Engine
==================
Multi-agent pipeline for automated LLM-based market research simulation.

Agent 1  — Audience Analyst & Survey Designer (2-phase: clarify → propose)
Simulation — Parallel persona-conditioned API calls (LiteLLM — model-agnostic)
Agent 2  — Aggregator & Strategist

Model configuration (via env vars or .env file):
  PRISM_AGENT_MODEL  — Agent 1 & 2  (default: claude-sonnet-4-6)
  PRISM_SIM_MODEL    — Simulation   (default: gemini/gemini-2.0-flash)

Supported providers (set matching API key env var):
  Anthropic  : ANTHROPIC_API_KEY   — claude-sonnet-4-6, claude-haiku-4-5-20251001
  Google     : GEMINI_API_KEY      — gemini/gemini-2.0-flash, gemini/gemini-1.5-pro
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import litellm
from dotenv import load_dotenv

load_dotenv()

AGENT_MODEL = os.getenv("PRISM_AGENT_MODEL", "claude-sonnet-4-6")
SIM_MODEL   = os.getenv("PRISM_SIM_MODEL",   "gemini/gemini-2.0-flash")

# Suppress litellm success logs
litellm.success_callback = []
litellm.set_verbose = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    name: str
    description: str       # persona description for system prompt
    weight: float          # population weight (0-1, all segments sum to 1)
    rationale: str         # why this segment is relevant

@dataclass
class SurveyQuestion:
    id: str
    text: str
    type: str              # "likert5" | "binary" | "wtp" | "open"
    scale_label: str = ""  # e.g. "1=Strongly Disagree, 5=Strongly Agree"

@dataclass
class SimulatedResponse:
    segment_name: str
    persona_detail: str
    question_id: str
    raw_response: str
    parsed_value: Any      # numeric for likert/wtp/binary, str for open

@dataclass
class SegmentResult:
    segment: Segment
    question_summaries: dict[str, Any]   # question_id -> aggregated stats
    open_themes: list[str]

@dataclass
class AnalysisOutput:
    segment_results: list[SegmentResult]
    overall_summary: dict[str, Any]
    recommendations: list[str]
    risk_flags: list[str]
    target_segment: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chat(model: str, system: str, user: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
    """Synchronous single-turn chat via LiteLLM."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    response = litellm.completion(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


async def _achat(model: str, system: str, user: str, max_tokens: int = 256, temperature: float = 1.0) -> str:
    """Async single-turn chat via LiteLLM."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    response = await litellm.acompletion(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def _strip_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Agent 1 — Phase A: Clarify
# ---------------------------------------------------------------------------

AGENT1_CLARIFY_SYSTEM = """\
You are a market research strategist. A user wants to simulate how different stakeholder
groups perceive a policy or product. Before designing the study, you must ask exactly
3 clarifying questions.

Focus your questions on:
1. Target geography / market
2. The decision the user is trying to inform (e.g. launch, policy change, pricing)
3. Any known stakeholder groups that matter most to them

Ask all 3 questions in a single, numbered list. Do not generate personas or survey
questions yet — only ask for clarification.
"""


def run_agent1_clarify(input_text: str) -> str:
    """Phase A — return 3 clarifying questions as a string."""
    return _chat(
        model=AGENT_MODEL,
        system=AGENT1_CLARIFY_SYSTEM,
        user=f"Policy/Product Description:\n\n{input_text}",
        max_tokens=512,
        temperature=0.5,
    )


# ---------------------------------------------------------------------------
# Agent 1 — Phase B: Propose
# ---------------------------------------------------------------------------

AGENT1_PROPOSE_SYSTEM = """\
You are a market research expert. Using the product/policy description and the user's
clarification answers, design a simulation study.

Your output must be ONLY valid JSON in this exact schema (no markdown fences, no extra text):
{
  "segments": [
    {
      "name": "short label",
      "description": "You are a [detailed persona — age, gender, location, income, occupation, lifestyle, relevant values and concerns]. Answer all survey questions as this person would, honestly and in character.",
      "weight": 0.25,
      "rationale": "why this segment matters for this product/policy"
    }
  ],
  "questions": [
    {
      "id": "q1",
      "text": "question text",
      "type": "likert5",
      "scale_label": "1=Strongly Disagree, 5=Strongly Agree"
    },
    {
      "id": "q2",
      "text": "question text",
      "type": "likert5",
      "scale_label": "1=Strongly Disagree, 5=Strongly Agree"
    },
    {
      "id": "q3",
      "text": "question text",
      "type": "binary",
      "scale_label": "Answer yes or no"
    },
    {
      "id": "q4",
      "text": "How much would you be willing to pay (in NT$) for [key feature]?",
      "type": "wtp",
      "scale_label": "Respond with a number only, in NT$"
    },
    {
      "id": "q5",
      "text": "In 1-2 sentences, what is your main concern or hope about [topic]?",
      "type": "open",
      "scale_label": ""
    }
  ]
}

Rules:
- Use 3 to 5 segments. Weights must sum to exactly 1.0.
- Prefer Likert-5 questions (quantifiable, supports statistical inference).
- Always end with exactly one open-ended question (type: "open").
- Persona descriptions must be vivid and realistic (2-4 sentences), written in second person.
- Questions must be directly relevant to the specific product/policy described.
- Do not use generic or placeholder text.
"""


def run_agent1_propose(input_text: str, clarifications: str = "") -> tuple[list[Segment], list[SurveyQuestion]]:
    """Phase B — generate segment + question proposal from description and optional clarifications."""
    user_content = f"Product/Policy Description:\n{input_text}"
    if clarifications:
        user_content += f"\n\nClarification Answers:\n{clarifications}"

    raw = _chat(model=AGENT_MODEL, system=AGENT1_PROPOSE_SYSTEM, user=user_content)
    data = _strip_json(raw)

    segments = [
        Segment(
            name=s["name"],
            description=s["description"],
            weight=float(s["weight"]),
            rationale=s["rationale"],
        )
        for s in data["segments"]
    ]
    questions = [
        SurveyQuestion(
            id=q["id"],
            text=q["text"],
            type=q["type"],
            scale_label=q.get("scale_label", ""),
        )
        for q in data["questions"]
    ]
    return segments, questions


def run_agent1(input_text: str) -> tuple[list[Segment], list[SurveyQuestion]]:
    """Single-shot Agent 1 (no clarification step — used in automated pipeline)."""
    return run_agent1_propose(input_text)


# ---------------------------------------------------------------------------
# Simulation Layer
# ---------------------------------------------------------------------------

def _build_question_instruction(q: SurveyQuestion) -> str:
    if q.type == "likert5":
        return (
            f"{q.text}\n"
            f"Rate on a scale of 1 to 5. {q.scale_label}. "
            f"Reply with a single integer (1, 2, 3, 4, or 5) and nothing else."
        )
    elif q.type == "binary":
        return (
            f"{q.text}\n"
            f"{q.scale_label}. Reply with exactly 'yes' or 'no' and nothing else."
        )
    elif q.type == "wtp":
        return (
            f"{q.text}\n"
            f"{q.scale_label}. Reply with a number only (no currency symbol, no text). "
            f"If you would not pay anything, reply with 0."
        )
    else:
        return f"{q.text}\nAnswer in 1-2 sentences. Be honest and specific."


def _parse_response(q: SurveyQuestion, raw: str) -> Any:
    text = raw.strip().lower()
    if q.type == "likert5":
        match = re.search(r"[1-5]", text)
        return int(match.group()) if match else None
    elif q.type == "binary":
        if "yes" in text:
            return 1
        elif "no" in text:
            return 0
        return None
    elif q.type == "wtp":
        match = re.search(r"\d[\d,]*", text)
        return float(match.group().replace(",", "")) if match else None
    else:
        return raw.strip()


async def _simulate_one(
    segment: Segment,
    question: SurveyQuestion,
    semaphore: asyncio.Semaphore,
    max_retries: int = 10,
) -> SimulatedResponse:
    instruction = _build_question_instruction(question)
    delay = 20.0
    for attempt in range(max_retries):
        try:
            async with semaphore:
                raw = await _achat(
                    model=SIM_MODEL,
                    system=segment.description,
                    user=instruction,
                    max_tokens=256,
                    temperature=1.0,
                )
            break
        except litellm.exceptions.RateLimitError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 120.0)
    return SimulatedResponse(
        segment_name=segment.name,
        persona_detail=segment.description[:80] + "...",
        question_id=question.id,
        raw_response=raw,
        parsed_value=_parse_response(question, raw),
    )


async def run_simulation_async(
    segments: list[Segment],
    questions: list[SurveyQuestion],
    responses_per_cell: int = 10,
    max_concurrent: int = 3,
) -> list[SimulatedResponse]:
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [
        _simulate_one(segment, question, semaphore)
        for segment in segments
        for question in questions
        for _ in range(responses_per_cell)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, SimulatedResponse)]


def run_simulation(
    segments: list[Segment],
    questions: list[SurveyQuestion],
    responses_per_cell: int = 10,
    max_concurrent: int = 3,
) -> list[SimulatedResponse]:
    return asyncio.run(
        run_simulation_async(segments, questions, responses_per_cell, max_concurrent)
    )


# ---------------------------------------------------------------------------
# Agent 2: Aggregator & Strategist
# ---------------------------------------------------------------------------

def _aggregate_responses(
    responses: list[SimulatedResponse],
    segments: list[Segment],
    questions: list[SurveyQuestion],
) -> list[SegmentResult]:
    seg_map = {s.name: s for s in segments}

    by_seg_q: dict[tuple[str, str], list[SimulatedResponse]] = {}
    for r in responses:
        by_seg_q.setdefault((r.segment_name, r.question_id), []).append(r)

    segment_results = []
    for seg in segments:
        q_summaries: dict[str, Any] = {}
        open_themes: list[str] = []

        for q in questions:
            cell = by_seg_q.get((seg.name, q.id), [])
            values = [r.parsed_value for r in cell if r.parsed_value is not None]

            if q.type in ("likert5", "wtp"):
                if values:
                    numeric = [float(v) for v in values]
                    q_summaries[q.id] = {
                        "type": q.type,
                        "question": q.text,
                        "n": len(numeric),
                        "mean": round(sum(numeric) / len(numeric), 2),
                        "min": round(min(numeric), 2),
                        "max": round(max(numeric), 2),
                    }
            elif q.type == "binary":
                if values:
                    q_summaries[q.id] = {
                        "type": "binary",
                        "question": q.text,
                        "n": len(values),
                        "pct_yes": round(100 * sum(values) / len(values), 1),
                    }
            else:
                open_themes.extend(r.raw_response for r in cell if r.raw_response)

        segment_results.append(SegmentResult(
            segment=seg_map[seg.name],
            question_summaries=q_summaries,
            open_themes=open_themes[:3],
        ))

    return segment_results


AGENT2_SYSTEM = """\
You are a senior market research analyst. Based on the survey simulation results below,
produce a structured strategic report.

Return ONLY valid JSON with this schema (no markdown fences):
{
  "overall_summary": {
    "weighted_reception_score": 3.4,
    "key_insight": "one-sentence headline finding"
  },
  "recommendations": [
    "actionable recommendation 1",
    "actionable recommendation 2",
    "actionable recommendation 3"
  ],
  "risk_flags": [
    "risk or concern 1",
    "risk or concern 2"
  ],
  "target_segment": "name of the most receptive segment"
}

Be specific and ground every recommendation in the data. Do not be generic.
"""


def run_agent2(
    segment_results: list[SegmentResult],
    questions: list[SurveyQuestion],
    input_text: str,
) -> AnalysisOutput:
    summary_lines = [f"Product/Policy: {input_text}\n"]
    for sr in segment_results:
        summary_lines.append(f"\nSegment: {sr.segment.name} (weight={sr.segment.weight:.0%})")
        for qid, stats in sr.question_summaries.items():
            q_text = stats.get("question", qid)
            if stats["type"] == "likert5":
                summary_lines.append(f"  [{qid}] {q_text[:60]} -> mean={stats['mean']}/5 (n={stats['n']})")
            elif stats["type"] == "binary":
                summary_lines.append(f"  [{qid}] {q_text[:60]} -> {stats['pct_yes']}% yes (n={stats['n']})")
            elif stats["type"] == "wtp":
                summary_lines.append(f"  [{qid}] {q_text[:60]} -> mean WTP=NT${stats['mean']} (n={stats['n']})")
        for t in sr.open_themes[:2]:
            summary_lines.append(f"  [open] \"{t[:120]}\"")

    raw = _chat(
        model=AGENT_MODEL,
        system=AGENT2_SYSTEM,
        user="\n".join(summary_lines),
        max_tokens=1024,
        temperature=0.5,
    )
    data = _strip_json(raw)

    return AnalysisOutput(
        segment_results=segment_results,
        overall_summary=data.get("overall_summary", {}),
        recommendations=data.get("recommendations", []),
        risk_flags=data.get("risk_flags", []),
        target_segment=data.get("target_segment", ""),
    )


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    input_text: str,
    responses_per_cell: int = 10,
    progress_callback=None,
    clarifications: str = "",
) -> AnalysisOutput:
    """
    End-to-end pipeline.
    Pass clarifications (from run_agent1_clarify user answers) for richer personas.
    progress_callback(step: str, pct: float) called at each stage.
    """
    def cb(step, pct):
        if progress_callback:
            progress_callback(step, pct)

    cb("Agent 1: Analyzing audience and designing survey...", 0.05)
    segments, questions = run_agent1_propose(input_text, clarifications)

    cb("Simulation: Running synthetic respondents...", 0.25)
    responses = run_simulation(segments, questions, responses_per_cell=responses_per_cell)

    cb("Aggregating results...", 0.80)
    segment_results = _aggregate_responses(responses, segments, questions)

    cb("Agent 2: Generating strategic recommendations...", 0.90)
    output = run_agent2(segment_results, questions, input_text)

    cb("Done.", 1.0)
    return output
