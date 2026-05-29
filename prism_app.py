"""
Prism — Web UI (Noble Quill rewrite)
=====================================
Four-phase Streamlit app: setup → clarify → run → results.
Multi-page via st.navigation with inline AppPage objects.

Run with:  streamlit run prism_app.py
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

from prism_engine import (
    AnalysisOutput,
    ClarifyQuestion,
    MediaHeadline,
    Segment,
    SurveyQuestion,
    _aggregate_responses,
    analyze_run_quality,
    configure_models,
    estimate_request_count,
    format_clarifications,
    format_duration,
    get_model_config,
    run_agent1_clarify,
    run_agent1_propose,
    run_agent2,
    run_simulation,
    run_media_agent,
)
from prism_session import (
    clarify_from_dict,
    clarify_to_dict,
    export_zip,
    import_zip,
    list_runs,
    load_manifest,
    load_responses,
    make_run_id,
    question_from_dict,
    question_to_dict,
    save_manifest,
    save_responses,
    segment_from_dict,
    segment_to_dict,
)
from prism_viz import (
    plotly_grouped_bar,
    plotly_heatmap,
    plotly_pie,
    plotly_segment_bar,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Prism — AI Market Research",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ_TAIPEI = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# Example inputs (preserved from original app)
# ---------------------------------------------------------------------------

EXAMPLES = {
    "Fertility Subsidy (Taiwan)": (
        "A government policy offering NT$200,000 cash subsidy per child for the first two "
        "children, targeted at married couples aged 25–40 living in major urban centers "
        "(Taipei, Taichung, Kaohsiung). The subsidy is paid in installments over 3 years "
        "and is means-tested (household income below NT$1.5M/year)."
    ),
    "Premium Co-Working App": (
        "A subscription app for freelancers and remote workers in Taiwan that provides "
        "curated co-working space bookings, community networking events, and AI-powered "
        "productivity tools. Monthly subscription priced at NT$990. Targets professionals "
        "aged 25–40 who work remotely at least 3 days per week."
    ),
    "Electric Scooter Trade-In Program": (
        "A government-subsidized program offering NT$8,000 trade-in rebate for owners of "
        "gasoline scooters who switch to an electric model. Partnered with Gogoro and "
        "iRent. Available to scooter owners in Taiwan's six largest cities. Riders must "
        "complete the swap within 6 months of registration."
    ),
}

PROVIDER_LABELS = {
    "gemini": "Gemini",
    "openai": "OpenAI",
    "anthropic": "Claude",
}

CHAT_MODEL_OPTIONS = {
    "gemini": [
        {"label": "Gemini 3.1 Flash Lite (15 RPM conservative)", "model": "gemini/gemini-3.1-flash-lite", "rpm": 15},
        {"label": "Gemini 2.5 Flash Lite (15 RPM free tier)", "model": "gemini/gemini-2.5-flash-lite", "rpm": 15},
    ],
    "openai": [
        {"label": "GPT-5.5 (500 RPM Tier 1)", "model": "gpt-5.5", "rpm": 500},
        {"label": "GPT-5.5 Pro (50 RPM Tier 1)", "model": "gpt-5.5-pro", "rpm": 50},
        {"label": "GPT-5.4 (500 RPM Tier 1)", "model": "gpt-5.4", "rpm": 500},
        {"label": "GPT-5.4 Mini (500 RPM Tier 1)", "model": "gpt-5.4-mini", "rpm": 500},
        {"label": "GPT-5.4 Nano (500 RPM Tier 1)", "model": "gpt-5.4-nano", "rpm": 500},
    ],
    "anthropic": [
        {"label": "Claude Opus 4.8 (50 RPM Tier 1)", "model": "anthropic/claude-opus-4-8", "rpm": 50},
        {"label": "Claude Sonnet 4.6 (50 RPM Tier 1)", "model": "anthropic/claude-sonnet-4-6", "rpm": 50},
        {"label": "Claude Haiku 4.5 (50 RPM Tier 1)", "model": "anthropic/claude-haiku-4-5-20251001", "rpm": 50},
    ],
}

EMBED_MODEL_OPTIONS = {
    "gemini": [
        {"label": "Gemini Embedding (15 RPM conservative)", "model": "gemini/gemini-embedding-001", "rpm": 15},
    ],
    "openai": [
        {"label": "text-embedding-3-small (3000 RPM Tier 1)", "model": "text-embedding-3-small", "rpm": 3000},
        {"label": "text-embedding-3-large (3000 RPM Tier 1)", "model": "text-embedding-3-large", "rpm": 3000},
    ],
}

DEFAULT_PROVIDER = "gemini"
DEFAULT_EMBED_PROVIDER = "gemini"


def _option_for_model(options: list[dict], model: str) -> dict | None:
    return next((opt for opt in options if opt["model"] == model), None)


def _select_model_option(label: str, options: list[dict], current_model: str, key: str) -> tuple[str, int | None]:
    labels = [opt["label"] for opt in options] + ["Custom"]
    current_option = _option_for_model(options, current_model)
    index = labels.index(current_option["label"]) if current_option else len(labels) - 1
    selected_label = st.selectbox(label, labels, index=index, key=f"{key}_select")
    if selected_label == "Custom":
        return st.text_input("Custom model", value=current_model, key=f"{key}_custom"), None
    selected = next(opt for opt in options if opt["label"] == selected_label)
    return selected["model"], int(selected["rpm"])


def _provider_key_label(provider: str) -> tuple[str, str]:
    if provider == "openai":
        return "OpenAI API key", "sk-..."
    if provider == "anthropic":
        return "Anthropic API key", "sk-ant-..."
    return "Google Gemini API key", "AIza..."


def _normalize_provider(provider: str | None, default: str = DEFAULT_PROVIDER) -> str:
    value = (provider or default).lower()
    if value in ("google", "gemini"):
        return "gemini"
    if value in ("claude", "anthropic"):
        return "anthropic"
    if value == "openai":
        return "openai"
    return default


def _extract_rpm_limit(response) -> float | None:
    """Best-effort extraction of request RPM from provider response headers."""
    header_candidates = []
    for attr in ("headers", "_response_headers"):
        headers = getattr(response, attr, None)
        if headers:
            header_candidates.append(headers)
    hidden = getattr(response, "_hidden_params", None)
    if hidden is None and isinstance(response, dict):
        hidden = response.get("_hidden_params")
    if isinstance(hidden, dict):
        for key in ("headers", "response_headers"):
            if hidden.get(key):
                header_candidates.append(hidden[key])

    for headers in header_candidates:
        if hasattr(headers, "items"):
            normalized = {str(k).lower(): v for k, v in headers.items()}
        else:
            continue
        for key in ("x-ratelimit-limit-requests", "anthropic-ratelimit-requests-limit"):
            if key in normalized:
                try:
                    return float(normalized[key])
                except (TypeError, ValueError):
                    continue
    return None

# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def _ss_get(key, default=None):
    return st.session_state.get(key, default)

def _ss_set(key, val):
    st.session_state[key] = val

def _init_ss():
    model_config = get_model_config()
    legacy_key = st.session_state.get("api_key", "")
    defaults = {
        "phase": "setup",
        "api_key": "",
        "chat_provider": DEFAULT_PROVIDER,
        "embed_provider": DEFAULT_EMBED_PROVIDER,
        "chat_api_key": legacy_key,
        "embed_api_key": "",
        "use_same_key_for_embedding": True,
        "key_valid": None,       # None=untested, True=ok, False=failed
        "embed_key_valid": None,
        "n_per_cell": 8,
        "run_id": None,
        "input_text": "",
        "clarify_questions": [],  # list[ClarifyQuestion]
        "clarify_answers": {},
        "segments": [],
        "questions": [],
        "responses": [],
        "seg_results": [],
        "agent2_output": None,
        "model_agent": model_config["agent_model"],
        "model_sim": model_config["sim_model"],
        "model_embed": model_config["embed_model"],
        "response_language": model_config["response_language"],
        "requests_per_minute": float(model_config["requests_per_minute"]),
        "headlines": [],
        "quality_report": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_ss()


def _apply_model_config():
    configure_models(
        agent_model=_ss_get("model_agent"),
        sim_model=_ss_get("model_sim"),
        embed_model=_ss_get("model_embed"),
        response_language=_ss_get("response_language"),
        requests_per_minute=_ss_get("requests_per_minute"),
    )


def _effective_chat_api_key() -> str:
    return _ss_get("chat_api_key") or _ss_get("api_key", "")


def _effective_embed_api_key() -> str:
    chat_provider = _ss_get("chat_provider", DEFAULT_PROVIDER)
    embed_provider = _ss_get("embed_provider", DEFAULT_EMBED_PROVIDER)
    same_key_allowed = chat_provider == embed_provider and chat_provider in EMBED_MODEL_OPTIONS
    if same_key_allowed and _ss_get("use_same_key_for_embedding", True):
        return _effective_chat_api_key()
    return _ss_get("embed_api_key", "")


def _ssr_questions(questions: list[SurveyQuestion]) -> list[SurveyQuestion]:
    return [q for q in questions if q.type == "likert5" and q.use_ssr]

# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def _build_manifest(phase: str) -> dict:
    """Build a manifest dict from current session state (no api_key)."""
    run_id = _ss_get("run_id") or make_run_id(_ss_get("n_per_cell"))
    _ss_set("run_id", run_id)
    agent2_obj = _ss_get("agent2_output")
    agent2_dict = {
        "overall_summary": agent2_obj.overall_summary,
        "recommendations": agent2_obj.recommendations,
        "risk_flags": agent2_obj.risk_flags,
        "target_segment": agent2_obj.target_segment,
    } if agent2_obj else {}
    return {
        "id": run_id,
        "title": (_ss_get("input_text") or "")[:80],
        "created_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
        "phase": phase,
        "input_text": _ss_get("input_text", ""),
        "clarify_questions": [clarify_to_dict(q) for q in _ss_get("clarify_questions", [])],
        "clarify_answers": _ss_get("clarify_answers", {}),
        "segments": [segment_to_dict(s) for s in _ss_get("segments", [])],
        "questions": [question_to_dict(q) for q in _ss_get("questions", [])],
        "n_per_cell": _ss_get("n_per_cell", 8),
        "chat_provider": _ss_get("chat_provider", DEFAULT_PROVIDER),
        "embed_provider": _ss_get("embed_provider", DEFAULT_EMBED_PROVIDER),
        "model_agent": _ss_get("model_agent", get_model_config()["agent_model"]),
        "model_sim": _ss_get("model_sim", get_model_config()["sim_model"]),
        "model_embed": _ss_get("model_embed", get_model_config()["embed_model"]),
        "response_language": _ss_get("response_language", get_model_config()["response_language"]),
        "requests_per_minute": _ss_get("requests_per_minute", float(get_model_config()["requests_per_minute"])),
        "headlines": [{"platform": h.platform, "content": h.content, "sentiment": h.sentiment} for h in _ss_get("headlines", [])],
        "provider": _ss_get("chat_provider", DEFAULT_PROVIDER),
        "agent2_output": agent2_dict,
        "stats": {
            "response_count": len(_ss_get("responses", [])),
            "quality_report": _ss_get("quality_report", {}),
        },
    }


def _load_run_into_session(manifest: dict):
    """Restore session state from a manifest."""
    _ss_set("run_id", manifest["id"])
    _ss_set("input_text", manifest.get("input_text", ""))
    _ss_set("clarify_questions", [clarify_from_dict(q) for q in manifest.get("clarify_questions", [])])
    _ss_set("clarify_answers", manifest.get("clarify_answers", {}))
    _ss_set("segments", [segment_from_dict(s) for s in manifest.get("segments", [])])
    _ss_set("questions", [question_from_dict(q) for q in manifest.get("questions", [])])
    _ss_set("n_per_cell", manifest.get("n_per_cell", 8))
    model_config = get_model_config()
    _ss_set("chat_provider", _normalize_provider(manifest.get("chat_provider", manifest.get("provider", DEFAULT_PROVIDER))))
    _ss_set("embed_provider", _normalize_provider(manifest.get("embed_provider", DEFAULT_EMBED_PROVIDER), DEFAULT_EMBED_PROVIDER))
    _ss_set("model_agent", manifest.get("model_agent", model_config["agent_model"]))
    _ss_set("model_sim", manifest.get("model_sim", model_config["sim_model"]))
    _ss_set("model_embed", manifest.get("model_embed", model_config["embed_model"]))
    _ss_set("response_language", manifest.get("response_language", model_config["response_language"]))
    _ss_set("requests_per_minute", manifest.get("requests_per_minute", float(model_config["requests_per_minute"])))
    _apply_model_config()
    _ss_set("headlines", [MediaHeadline(**h) if isinstance(h, dict) else h for h in manifest.get("headlines", [])])
    responses = load_responses(manifest["id"])
    _ss_set("responses", responses)
    _ss_set("quality_report", manifest.get("stats", {}).get("quality_report", {}))
    agent2 = manifest.get("agent2_output") or {}
    if agent2:
        seg_results = _aggregate_from_manifest(manifest)
        _ss_set("seg_results", seg_results)
        _ss_set("agent2_output", AnalysisOutput(
            segment_results=seg_results,
            overall_summary=agent2.get("overall_summary", {}),
            recommendations=agent2.get("recommendations", []),
            risk_flags=agent2.get("risk_flags", []),
            target_segment=agent2.get("target_segment", ""),
        ))
    _ss_set("phase", manifest.get("phase", "results"))


def _aggregate_from_manifest(manifest: dict):
    """Rebuild segment results from saved responses when available."""
    segments = [segment_from_dict(s) for s in manifest.get("segments", [])]
    questions = [question_from_dict(q) for q in manifest.get("questions", [])]
    responses = load_responses(manifest["id"])
    if responses and segments and questions:
        return _aggregate_responses(responses, segments, questions)
    from prism_engine import SegmentResult
    return [SegmentResult(segment=s, question_summaries={}, open_themes=[]) for s in segments]


def _build_report_markdown(
    output: AnalysisOutput,
    segments: list[Segment],
    questions: list[SurveyQuestion],
    quality: dict,
) -> str:
    overall = output.overall_summary or {}
    warnings = quality.get("warnings", []) if quality else []
    stable_note = (
        "Prism uses synthetic respondents. Treat these outputs as directional "
        "hypotheses for follow-up validation, not measured public opinion."
    )
    lines = [
        "# Prism Simulation Report",
        "",
        f"Run ID: `{_ss_get('run_id') or 'unsaved'}`",
        f"Reception score: `{overall.get('weighted_reception_score', 'N/A')}/5`",
        f"Target segment: `{output.target_segment or 'N/A'}`",
        "",
        "## Key Insight",
        "",
        overall.get("key_insight", "No key insight available."),
        "",
        "## Simulated Findings",
        "",
    ]

    for sr in output.segment_results:
        lines.append(f"### {sr.segment.name}")
        for qid, stats in sr.question_summaries.items():
            if qid == "__sdb_gaps__":
                for pair, gap in stats.items():
                    lines.append(f"- SDB gap `{pair}`: `{gap:+.2f}` anonymous minus named.")
                continue
            if stats.get("type") == "likert5":
                lines.append(f"- `{qid}` mean: `{stats.get('mean')}/5` (`n={stats.get('n')}`).")
            elif stats.get("type") == "multi_select":
                top = sorted(stats.get("rates", {}).items(), key=lambda x: -x[1])[:3]
                top_text = ", ".join(f"{k}: {v}%" for k, v in top)
                lines.append(f"- `{qid}` top selections: {top_text}.")
            elif stats.get("type") == "wtp":
                lines.append(f"- `{qid}` mean numeric response: `NT${stats.get('mean')}` (`n={stats.get('n')}`).")
        lines.append("")

    lines.extend([
        "## Recommendations",
        "",
    ])
    for rec in output.recommendations:
        lines.append(f"- {rec}")

    lines.extend([
        "",
        "## Risk Flags",
        "",
    ])
    for flag in output.risk_flags:
        lines.append(f"- {flag}")

    lines.extend([
        "",
        "## Run Quality",
        "",
        f"- Responses: `{quality.get('actual_responses', 0)}/{quality.get('expected_responses', 0)}`",
        f"- Duplicate cell rate: `{quality.get('duplicate_cell_rate', 0) * 100:.0f}%`",
        f"- Flat Likert cell rate: `{quality.get('all_same_likert_rate', 0) * 100:.0f}%`",
        f"- SSR Likert questions: `{quality.get('ssr_question_count', 0)}`",
        f"- SDB pairs: `{quality.get('sdb_pair_count', 0)}`",
        "",
        "## Limitations",
        "",
        f"- {stable_note}",
    ])
    for warning in warnings:
        lines.append(f"- Quality warning: {warning}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar():
    with st.sidebar:
        st.title("Prism")
        st.caption("Policy Perception Simulator")
        st.divider()

        # --- Provider and API keys ---
        st.subheader("Provider")
        provider_values = list(PROVIDER_LABELS.keys())
        current_provider = _normalize_provider(_ss_get("chat_provider", DEFAULT_PROVIDER))
        if current_provider != _ss_get("chat_provider", DEFAULT_PROVIDER):
            _ss_set("chat_provider", current_provider)
        provider_label = st.selectbox(
            "Chat provider",
            [PROVIDER_LABELS[p] for p in provider_values],
            index=provider_values.index(current_provider) if current_provider in provider_values else 0,
        )
        chat_provider = next(p for p, label in PROVIDER_LABELS.items() if label == provider_label)
        if chat_provider != current_provider:
            _ss_set("chat_provider", chat_provider)
            chat_default = CHAT_MODEL_OPTIONS[chat_provider][0]
            _ss_set("model_agent", chat_default["model"])
            _ss_set("model_sim", chat_default["model"])
            _ss_set("requests_per_minute", float(chat_default["rpm"]))
            if chat_provider in EMBED_MODEL_OPTIONS:
                _ss_set("embed_provider", chat_provider)
                _ss_set("model_embed", EMBED_MODEL_OPTIONS[chat_provider][0]["model"])
                _ss_set("use_same_key_for_embedding", True)
            else:
                _ss_set("embed_provider", "openai")
                _ss_set("model_embed", EMBED_MODEL_OPTIONS["openai"][0]["model"])
                _ss_set("use_same_key_for_embedding", False)
            _ss_set("key_valid", None)
            _ss_set("embed_key_valid", None)
            _ss_set("detected_rpm", None)
            _apply_model_config()
            st.rerun()

        chat_label, chat_placeholder = _provider_key_label(chat_provider)
        raw_chat_key = st.text_input(
            chat_label,
            value=_ss_get("chat_api_key", _ss_get("api_key", "")),
            type="password",
            placeholder=chat_placeholder,
            help="Stored only in this browser session. Never written to disk.",
        )
        if raw_chat_key != _ss_get("chat_api_key"):
            _ss_set("chat_api_key", raw_chat_key)
            _ss_set("api_key", raw_chat_key)  # legacy compatibility
            _ss_set("key_valid", None)
            _ss_set("detected_rpm", None)

        embed_provider_values = list(EMBED_MODEL_OPTIONS.keys())
        current_embed_provider = _normalize_provider(_ss_get("embed_provider", DEFAULT_EMBED_PROVIDER), DEFAULT_EMBED_PROVIDER)
        if current_embed_provider != _ss_get("embed_provider", DEFAULT_EMBED_PROVIDER):
            _ss_set("embed_provider", current_embed_provider)
        if current_embed_provider not in embed_provider_values:
            current_embed_provider = DEFAULT_EMBED_PROVIDER
        embed_label = st.selectbox(
            "Embedding provider for SSR",
            [PROVIDER_LABELS[p] for p in embed_provider_values],
            index=embed_provider_values.index(current_embed_provider),
            help="Claude does not provide embeddings here, so SSR needs OpenAI or Gemini embeddings.",
        )
        embed_provider = next(p for p, label in PROVIDER_LABELS.items() if label == embed_label)
        if embed_provider != _ss_get("embed_provider"):
            _ss_set("embed_provider", embed_provider)
            _ss_set("model_embed", EMBED_MODEL_OPTIONS[embed_provider][0]["model"])
            _ss_set("use_same_key_for_embedding", chat_provider == embed_provider)
            _ss_set("embed_key_valid", None)
            _ss_set("detected_rpm", None)
            _apply_model_config()
            st.rerun()

        same_key_allowed = chat_provider == embed_provider and chat_provider in EMBED_MODEL_OPTIONS
        if same_key_allowed:
            use_same = st.checkbox(
                "Use same key for chat and embeddings",
                value=_ss_get("use_same_key_for_embedding", True),
            )
            if use_same != _ss_get("use_same_key_for_embedding"):
                _ss_set("use_same_key_for_embedding", use_same)
                _ss_set("embed_key_valid", None)
        else:
            _ss_set("use_same_key_for_embedding", False)
            st.caption("Embeddings need a separate OpenAI or Gemini key for this chat provider.")

        if not _ss_get("use_same_key_for_embedding", True):
            embed_key_label, embed_placeholder = _provider_key_label(embed_provider)
            raw_embed_key = st.text_input(
                f"{embed_key_label} for embeddings",
                value=_ss_get("embed_api_key", ""),
                type="password",
                placeholder=embed_placeholder,
                help="Used only for SSR/free-text Likert embedding calls.",
            )
            if raw_embed_key != _ss_get("embed_api_key"):
                _ss_set("embed_api_key", raw_embed_key)
                _ss_set("embed_key_valid", None)
                _ss_set("detected_rpm", None)

        st.caption("API keys stay in browser memory for this session only.")

        col_test_chat, col_test_embed = st.columns([1, 1])
        with col_test_chat:
            if st.button("Test chat", width="stretch"):
                if not _effective_chat_api_key():
                    _ss_set("key_valid", False)
                else:
                    with st.spinner("Testing chat..."):
                        try:
                            import litellm
                            resp = litellm.completion(
                                model=_ss_get("model_agent"),
                                messages=[{"role": "user", "content": "Hi"}],
                                max_tokens=1,
                                api_key=_effective_chat_api_key(),
                            )
                            detected_rpm = _extract_rpm_limit(resp)
                            if detected_rpm:
                                _ss_set("requests_per_minute", detected_rpm)
                                _ss_set("detected_rpm", detected_rpm)
                            _ss_set("key_valid", True)
                        except Exception:
                            _ss_set("key_valid", False)
                    st.rerun()
        with col_test_embed:
            if st.button("Test embed", width="stretch"):
                if not _effective_embed_api_key():
                    _ss_set("embed_key_valid", False)
                else:
                    with st.spinner("Testing embedding..."):
                        try:
                            import litellm
                            resp = litellm.embedding(
                                model=_ss_get("model_embed"),
                                input=["Prism embedding test"],
                                api_key=_effective_embed_api_key(),
                            )
                            detected_rpm = _extract_rpm_limit(resp)
                            if detected_rpm:
                                _ss_set("requests_per_minute", detected_rpm)
                                _ss_set("detected_rpm", detected_rpm)
                            _ss_set("embed_key_valid", True)
                        except Exception:
                            _ss_set("embed_key_valid", False)
                    st.rerun()

        chat_status, embed_status = st.columns([1, 1])
        with chat_status:
            kv = _ss_get("key_valid")
            if kv is True:
                st.success("Chat valid")
            elif kv is False:
                st.error("Chat invalid")
            else:
                st.caption("Chat not tested")
        with embed_status:
            ev = _ss_get("embed_key_valid")
            if ev is True:
                st.success("Embed valid")
            elif ev is False:
                st.error("Embed invalid")
            elif _ss_get("use_same_key_for_embedding", True):
                st.caption("Embed uses chat key")
            else:
                st.caption("Embed not tested")
        if _ss_get("detected_rpm"):
            st.caption(f"Detected RPM from response headers: {_ss_get('detected_rpm'):g}")

        st.divider()

        # --- Model config ---
        with st.expander("Advanced model config"):
            chat_options = CHAT_MODEL_OPTIONS[_normalize_provider(_ss_get("chat_provider", DEFAULT_PROVIDER))]
            embed_options = EMBED_MODEL_OPTIONS[_normalize_provider(_ss_get("embed_provider", DEFAULT_EMBED_PROVIDER), DEFAULT_EMBED_PROVIDER)]
            model_agent, agent_rpm = _select_model_option(
                "Agent model", chat_options, _ss_get("model_agent"), "agent_model"
            )
            model_sim, sim_rpm = _select_model_option(
                "Simulation model", chat_options, _ss_get("model_sim"), "sim_model"
            )
            model_embed, embed_rpm = _select_model_option(
                "Embedding model", embed_options, _ss_get("model_embed"), "embed_model"
            )
            suggested_rpms = [rpm for rpm in [agent_rpm, sim_rpm, embed_rpm] if rpm]
            suggested_rpm = min(suggested_rpms) if suggested_rpms else None
            rpm = st.number_input(
                "Requests per minute used for pacing",
                min_value=0.0,
                max_value=30000.0,
                value=float(_ss_get("requests_per_minute", 15)),
                step=5.0,
                help="Model labels show official Tier 1 or conservative RPM. This manual value controls Prism's actual pacing.",
            )
            if suggested_rpm and st.button(f"Use selected-model RPM ({suggested_rpm})", width="stretch"):
                _ss_set("requests_per_minute", float(suggested_rpm))
                _apply_model_config()
                st.rerun()
            response_language = st.selectbox(
                "Response language",
                ["match_input", "traditional_chinese", "english"],
                index=["match_input", "traditional_chinese", "english"].index(
                    _ss_get("response_language")
                    if _ss_get("response_language") in ["match_input", "traditional_chinese", "english"]
                    else "match_input"
                ),
            )
            if model_agent != _ss_get("model_agent"):
                _ss_set("model_agent", model_agent)
            if model_sim != _ss_get("model_sim"):
                _ss_set("model_sim", model_sim)
            if model_embed != _ss_get("model_embed"):
                _ss_set("model_embed", model_embed)
            if response_language != _ss_get("response_language"):
                _ss_set("response_language", response_language)
            if rpm != _ss_get("requests_per_minute"):
                _ss_set("requests_per_minute", float(rpm))
            _apply_model_config()
            st.caption("RPM is account-tier dependent. Use your provider console as source of truth.")

        # --- Simulation settings ---
        st.subheader("Simulation Settings")
        n = st.slider(
            "Responses per segment × question",
            min_value=3, max_value=30,
            value=_ss_get("n_per_cell", 8),
            help="More → more stable estimates, higher cost.",
        )
        _ss_set("n_per_cell", n)

        st.divider()

        # --- Session list ---
        st.subheader("Past Runs")
        if st.button("New session", width="stretch"):
            for k in ["phase", "run_id", "input_text", "clarify_questions", "clarify_answers",
                      "segments", "questions", "responses", "seg_results", "agent2_output",
                      "headlines", "quality_report", "run_estimate", "preview_del_qs"]:
                st.session_state.pop(k, None)
            _init_ss()
            st.rerun()

        runs = list_runs()
        if runs:
            for m in runs[:10]:
                ts = m.get("created_at", "")[:16].replace("T", " ")
                n_seg = len(m.get("segments", []))
                label = f"{m.get('title', m['id'])[:30]} | {ts} | {n_seg}seg"
                if st.button(label, key=f"run_{m['id']}", width="stretch"):
                    _load_run_into_session(m)
                    st.rerun()
        else:
            st.caption("No saved runs yet.")

        # --- Import zip ---
        up = st.file_uploader("Import run (.zip)", type="zip", label_visibility="collapsed")
        if up is not None:
            try:
                run_id = import_zip(up.read())
                m = load_manifest(run_id)
                if m:
                    _load_run_into_session(m)
                    st.success(f"Imported {run_id}")
                    st.rerun()
            except Exception as e:
                st.error(f"Import failed: {e}")


# ---------------------------------------------------------------------------
# Phase: Setup
# ---------------------------------------------------------------------------

def page_setup():
    st.title("Prism")
    st.markdown(
        "Enter a product concept or policy proposal. The system simulates how different "
        "stakeholder groups perceive and respond to it — automatically."
    )

    col_input, col_example = st.columns([3, 1])

    with col_example:
        st.markdown("**Try an example:**")
        for label in EXAMPLES:
            if st.button(label, width="stretch", key=f"ex_{label}"):
                _ss_set("input_text", EXAMPLES[label])
                st.rerun()

    with col_input:
        input_text = st.text_area(
            "Product / Policy Description",
            value=_ss_get("input_text", ""),
            height=180,
            placeholder=(
                "Describe your product or policy in plain language. "
                "Include target audience, key features, pricing, and context."
            ),
        )
        if input_text:
            _ss_set("input_text", input_text)

    chat_api_key = _effective_chat_api_key()
    ready = bool(input_text and chat_api_key)

    if not chat_api_key:
        st.info("Enter your chat API key in the sidebar to continue.")

    if st.button("Next: Clarify →", type="primary", disabled=not ready):
        with st.spinner("Agent 1 is generating clarifying questions..."):
            try:
                _apply_model_config()
                questions = run_agent1_clarify(input_text, api_key=chat_api_key)
                _ss_set("clarify_questions", questions)
                _ss_set("clarify_answers", {})
                _ss_set("run_id", make_run_id(_ss_get("n_per_cell")))
                _ss_set("phase", "clarify")
                save_manifest(_build_manifest("clarify"))
                st.rerun()
            except Exception as e:
                st.error(f"Clarify failed: {e}")

    # How it works
    st.divider()
    st.markdown("""
### How it works

| Step | Agent | What happens |
|---|---|---|
| 1 | **Audience Analyst** | Reads your description, asks clarifying questions, generates 3–5 stakeholder segments and 12–15 survey questions |
| 2 | **Simulation Layer** | For each segment × question, runs parallel LLM calls with persona injection |
| 3 | **Strategist** | Aggregates results, computes SDB gaps, and generates actionable recommendations |

**Survey includes:** Likert-5 scales, anonymous/named SDB pair, multi-select, WTP, open-ended.
    """)


# ---------------------------------------------------------------------------
# Phase: Clarify
# ---------------------------------------------------------------------------

def page_clarify():
    st.title("Clarify Your Study")
    st.caption("Answer these questions to help Agent 1 design a more targeted survey.")

    cqs: list[ClarifyQuestion] = _ss_get("clarify_questions", [])
    answers: dict = _ss_get("clarify_answers", {})

    must_qs = [q for q in cqs if q.priority == "must"]
    nice_qs = [q for q in cqs if q.priority != "must"]

    def _render_question(q: ClarifyQuestion):
        label = q.text
        key = f"cq_{q.id}"
        skip_key = f"skip_{q.id}"

        # Skippable toggle
        skip = False
        if q.skippable:
            skip = st.checkbox("Let agent decide", key=skip_key, value=(answers.get(q.id) == "__SKIP__"))

        if skip:
            answers[q.id] = "__SKIP__"
            st.caption(f"*Will infer from context. ({q.why})*")
            return

        if q.answer_type == "single_select":
            opts = q.options if not q.allow_freeform else q.options + ["Other..."]
            val = st.radio(label, opts, key=key, help=q.why,
                           index=opts.index(answers.get(q.id)) if answers.get(q.id) in opts else 0)
            if val == "Other..." and q.allow_freeform:
                val = st.text_input("Specify:", key=f"{key}_other",
                                    value=answers.get(q.id) if answers.get(q.id) not in opts else "")
            answers[q.id] = val

        elif q.answer_type == "multi_select":
            existing = answers.get(q.id, [])
            if isinstance(existing, str):
                existing = [existing] if existing and existing != "__SKIP__" else []
            val = st.multiselect(label, q.options, default=existing, key=key, help=q.why)
            answers[q.id] = val

        elif q.answer_type == "number":
            existing_num = answers.get(q.id, 0)
            try:
                existing_num = float(existing_num)
            except (TypeError, ValueError):
                existing_num = 0
            val = st.number_input(label, value=existing_num, key=key, help=q.why)
            answers[q.id] = val

        else:  # text
            val = st.text_input(label, value=answers.get(q.id, ""), key=key,
                                help=q.why + (f" Suggestions: {', '.join(q.options)}" if q.options else ""))
            answers[q.id] = val

    # Render must questions
    for q in must_qs:
        with st.container(border=True):
            _render_question(q)

    # Render nice questions in expander
    if nice_qs:
        with st.expander("Optional refinements"):
            for q in nice_qs:
                with st.container(border=True):
                    _render_question(q)

    _ss_set("clarify_answers", answers)

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("← Back"):
            _ss_set("phase", "setup")
            st.rerun()
    with col_next:
        if st.button("Generate survey →", type="primary"):
            with st.spinner("Agent 1 is designing your survey..."):
                try:
                    _apply_model_config()
                    chat_api_key = _effective_chat_api_key()
                    clarif_text = format_clarifications(cqs, answers)
                    segments, questions = run_agent1_propose(
                        _ss_get("input_text"), clarif_text, api_key=chat_api_key
                    )

                    headlines = run_media_agent(_ss_get("input_text"), api_key=chat_api_key)
                    estimate = estimate_request_count(segments, questions, _ss_get("n_per_cell", 8))
                    _ss_set("run_estimate", estimate)
                    _ss_set("headlines", headlines)
                    _ss_set("segments", segments)
                    _ss_set("questions", questions)
                    _ss_set("responses", [])
                    _ss_set("seg_results", [])
                    _ss_set("agent2_output", None)
                    _ss_set("quality_report", {})
                    _ss_set("phase", "preview")
                    st.session_state.pop("preview_del_qs", None)
                    save_manifest(_build_manifest("preview"))
                    st.rerun()
                except Exception as e:
                    st.error(f"Survey generation failed: {e}")


# ---------------------------------------------------------------------------
# Phase: Preview
# ---------------------------------------------------------------------------

_Q_TYPES = ["likert5", "binary", "wtp", "open", "multi_select"]
_CONDITIONS = ["neutral", "anonymous", "named"]

TYPE_BADGE_CSS = {
    "likert5":      ("Likert 1–5",   "#F59E0B", "#fff"),
    "binary":       ("Yes / No",     "#10B981", "#fff"),
    "wtp":          ("WTP",          "#EC4899", "#fff"),
    "open":         ("Open",         "#6366F1", "#fff"),
    "multi_select": ("Multi-select", "#3B82F6", "#fff"),
}


def page_preview():
    st.title("Review Survey Design")
    st.caption("Edit segments or questions, then click **Run Simulation** to proceed.")

    headlines = _ss_get("headlines")
    if headlines:
        st.subheader("📰 Simulated Media Environment")
        for h in headlines:
            color = "green" if h.sentiment=="positive" else "red" if h.sentiment=="negative" else "gray"
            st.markdown(f"- **{h.platform}**: {h.content} (:{color}[{h.sentiment}])")
        st.divider()

    segments: list[Segment] = _ss_get("segments", [])
    questions: list[SurveyQuestion] = _ss_get("questions", [])
    estimate = estimate_request_count(segments, questions, _ss_get("n_per_cell", 8))
    _ss_set("run_estimate", estimate)

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Estimated Requests", estimate["total_requests"])
        c2.metric("Minimum Runtime", format_duration(estimate["estimated_min_seconds"]))
        c3.metric("SSR Likert Qs", sum(1 for q in questions if q.type == "likert5" and q.use_ssr))
        c4.metric("Rate Limit", estimate["rate_limit_summary"].split(" ")[0] + " RPM")
        if estimate["estimated_min_seconds"] >= 600:
            st.warning("This run is estimated to take more than 10 minutes under the current RPM limit.")
        if _ss_get("n_per_cell", 8) < 5:
            st.warning("n_per_cell is below 5. Use this as a smoke test, not final evidence.")

    if "preview_del_qs" not in st.session_state:
        st.session_state["preview_del_qs"] = set()

    tab_segs, tab_qs = st.tabs([
        f"Segments ({len(segments)})",
        f"Questions ({len(questions) - len(st.session_state['preview_del_qs'])})",
    ])

    # ---- Segments tab -------------------------------------------------------
    with tab_segs:
        new_segments: list[Segment] = []
        for i, seg in enumerate(segments):
            with st.container(border=True):
                col_name, col_w = st.columns([3, 1])
                with col_name:
                    name = st.text_input("Name", value=seg.name, key=f"ps_name_{i}")
                with col_w:
                    weight = st.number_input(
                        "Weight", value=float(seg.weight),
                        min_value=0.0, max_value=1.0, step=0.05,
                        key=f"ps_w_{i}",
                    )
                rationale = st.text_input("Rationale", value=seg.rationale, key=f"ps_rat_{i}")
                with st.expander("Persona description"):
                    desc = st.text_area(
                        "Persona", value=seg.description,
                        key=f"ps_desc_{i}", height=100, label_visibility="collapsed",
                    )
                new_segments.append(Segment(name=name, description=desc, weight=weight, rationale=rationale))

        total_w = sum(s.weight for s in new_segments)
        if abs(total_w - 1.0) > 0.01:
            col_warn, col_norm = st.columns([3, 1])
            with col_warn:
                st.warning(f"Weights sum to {total_w:.2f} — normalize before running.")
            with col_norm:
                if st.button("Normalize", width="stretch"):
                    if total_w > 0:
                        new_segments = [
                            Segment(s.name, s.description, round(s.weight / total_w, 4), s.rationale)
                            for s in new_segments
                        ]
                    _ss_set("segments", new_segments)
                    st.rerun()

        _ss_set("segments", new_segments)

    # ---- Questions tab ------------------------------------------------------
    with tab_qs:
        new_questions: list[SurveyQuestion] = []
        del_set: set = st.session_state["preview_del_qs"]

        for i, q in enumerate(questions):
            if i in del_set:
                continue
            badge_text, bg, fg = TYPE_BADGE_CSS.get(q.type, (q.type, "#ccc", "#333"))
            with st.container(border=True):
                col_id, col_badge, col_del = st.columns([3, 2, 1])
                with col_id:
                    st.markdown(f"**{q.id}**")
                with col_badge:
                    qtype = st.selectbox(
                        "Type",
                        _Q_TYPES,
                        index=_Q_TYPES.index(q.type) if q.type in _Q_TYPES else 0,
                        key=f"pq_type_{i}",
                        label_visibility="collapsed",
                    )
                with col_del:
                    if st.button("✕", key=f"pq_del_{i}", help="Remove this question"):
                        del_set.add(i)
                        st.session_state["preview_del_qs"] = del_set
                        st.rerun()

                text = st.text_area(
                    "Question text", value=q.text,
                    key=f"pq_text_{i}", height=68, label_visibility="collapsed",
                )

                col_cond, col_scale = st.columns(2)
                with col_cond:
                    cond = st.selectbox(
                        "Condition", _CONDITIONS,
                        index=_CONDITIONS.index(q.condition) if q.condition in _CONDITIONS else 0,
                        key=f"pq_cond_{i}",
                    )
                with col_scale:
                    scale = st.text_input(
                        "Scale label", value=q.scale_label or "",
                        key=f"pq_scale_{i}",
                    )

                opts = q.options
                if qtype == "multi_select":
                    opts_str = st.text_input(
                        "Options (comma-separated)",
                        value=", ".join(q.options),
                        key=f"pq_opts_{i}",
                    )
                    opts = [o.strip() for o in opts_str.split(",") if o.strip()]

                use_ssr = q.use_ssr
                anchors = list(q.anchors or [])
                if qtype == "likert5":
                    use_ssr = st.checkbox(
                        "Use SSR/free-text scoring",
                        value=q.use_ssr,
                        key=f"pq_ssr_{i}",
                        help="Collects a short free-text answer and maps it to a Likert score with embeddings.",
                    )
                    if use_ssr:
                        anchors_text = st.text_area(
                            "SSR anchors (one per line, low to high)",
                            value="\n".join(anchors),
                            key=f"pq_anchors_{i}",
                            height=92,
                        )
                        anchors = [a.strip() for a in anchors_text.splitlines() if a.strip()]
                else:
                    use_ssr = False
                    anchors = []

                new_questions.append(SurveyQuestion(
                    id=q.id, text=text, type=qtype,
                    scale_label=scale, options=opts, condition=cond,
                    use_ssr=use_ssr, anchors=anchors,
                ))

        _ss_set("questions", new_questions)

        remaining = len(new_questions)
        if remaining < len(questions):
            st.caption(f"{len(questions) - remaining} question(s) removed. They won't be run.")

    st.divider()
    col_back, col_spacer, col_run = st.columns([1, 2, 2])
    with col_back:
        if st.button("← Regenerate"):
            st.session_state.pop("preview_del_qs", None)
            _ss_set("phase", "clarify")
            st.rerun()
    with col_run:
        if st.button("▶ Run Simulation", type="primary", width="stretch"):
            st.session_state.pop("preview_del_qs", None)
            _ss_set("phase", "run")
            save_manifest(_build_manifest("run"))
            st.rerun()


# ---------------------------------------------------------------------------
# Phase: Run
# ---------------------------------------------------------------------------

def page_run():
    st.title("Running Study")

    segments: list[Segment] = _ss_get("segments", [])
    questions: list[SurveyQuestion] = _ss_get("questions", [])
    chat_api_key = _effective_chat_api_key()
    embed_api_key = _effective_embed_api_key()
    n_per_cell = _ss_get("n_per_cell", 8)
    if not _ss_get("run_id"):
        _ss_set("run_id", make_run_id(n_per_cell))
    if not chat_api_key:
        st.error("Chat API key is required to run the simulation.")
        return
    if _ssr_questions(questions) and not embed_api_key:
        st.error("SSR/free-text Likert questions need an embedding API key. Add one in the sidebar or turn off SSR in Preview.")
        return

    # Step 1 — Survey Design (already done)
    with st.container(border=True):
        st.markdown(f"**Step 1 — Survey Design** ✓ complete")
        st.caption(f"{len(segments)} segments, {len(questions)} questions")

    # Step 2 — Simulation
    with st.container(border=True):
        st.markdown("**Step 2 — Simulating Responses**")
        total_calls = len(segments) * len(questions) * n_per_cell
        estimate = estimate_request_count(segments, questions, n_per_cell)
        st.caption(
            f"Simulation calls: {total_calls}. Estimated total requests including SSR/analysis: "
            f"{estimate['total_requests']} ({format_duration(estimate['estimated_min_seconds'])} minimum at "
            f"{estimate['rate_limit_summary']})."
        )

        prog_bar = st.progress(0)
        prog_text = st.empty()

        responses_holder = {}
        error_holder = {}

        current_headlines = _ss_get("headlines")
        model_agent = _ss_get("model_agent")
        model_sim = _ss_get("model_sim")
        model_embed = _ss_get("model_embed")
        response_language = _ss_get("response_language")
        requests_per_minute = _ss_get("requests_per_minute")
        _ss_set("quality_report", {})

        def _run_sim():
            print("\nStarting background simulation thread.")

            def _cb(done, total):
                responses_holder["completed"] = done

            try:
                configure_models(model_agent, model_sim, model_embed, response_language, requests_per_minute)
                resp = run_simulation(
                    segments, questions,
                    headlines=current_headlines,
                    responses_per_cell=n_per_cell,
                    chat_api_key=chat_api_key,
                    embed_api_key=embed_api_key,
                    progress_callback=_cb,
                )
                responses_holder["result"] = resp
            except Exception as e:
                error_holder["err"] = str(e)
                print(f"Simulation failed: {e}")

        thread = threading.Thread(target=_run_sim, daemon=True)
        thread.start()

        # Poll until done
        while thread.is_alive():
            done = responses_holder.get("completed", 0)
            pct = done / total_calls if total_calls > 0 else 0
            prog_bar.progress(min(pct, 0.99))
            prog_text.caption(f"Collected {done}/{total_calls} responses...")
            time.sleep(0.5)

        thread.join()

        if "err" in error_holder:
            st.error(f"Simulation failed: {error_holder['err']}")
            return

        prog_bar.progress(1.0)
        prog_text.caption(f"Simulation complete — {len(responses_holder['result'])} responses")
        responses = responses_holder["result"]
        _ss_set("responses", responses)
        quality = analyze_run_quality(responses, segments, questions, n_per_cell)
        _ss_set("quality_report", quality)
        save_responses(_ss_get("run_id"), responses)

    # Step 3 — Agent 2
    with st.container(border=True):
        st.markdown("**Step 3 — Strategic Analysis**")
        with st.spinner("Agent 2 is generating recommendations..."):
            try:
                _apply_model_config()
                seg_results = _aggregate_responses(responses, segments, questions)
                output = run_agent2(seg_results, questions, _ss_get("input_text"), api_key=chat_api_key)
                _ss_set("seg_results", seg_results)
                _ss_set("agent2_output", output)
                st.success("Analysis complete.")
            except Exception as e:
                st.error(f"Agent 2 failed: {e}")
                return

    # Save and advance
    save_manifest(_build_manifest("results"))
    _ss_set("phase", "results")
    st.rerun()


# ---------------------------------------------------------------------------
# Phase: Results
# ---------------------------------------------------------------------------

def page_results():
    output: AnalysisOutput | None = _ss_get("agent2_output")
    segments: list[Segment] = _ss_get("segments", [])
    questions: list[SurveyQuestion] = _ss_get("questions", [])
    responses = _ss_get("responses", [])
    quality = _ss_get("quality_report", {})
    if responses and not quality:
        quality = analyze_run_quality(responses, segments, questions, _ss_get("n_per_cell", 8))
        _ss_set("quality_report", quality)

    if output is None:
        st.warning("No results available. Run a study first.")
        return

    overall = output.overall_summary
    reception = overall.get("weighted_reception_score", "—")
    key_insight = overall.get("key_insight", "")

    # --- Top metrics ---
    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Reception Score",
        f"{reception}/5" if isinstance(reception, (int, float)) else reception,
        help="Weighted average Likert score across all segments",
    )
    m2.metric("Target Segment", output.target_segment or "—")
    m3.metric("Total Responses", len(responses))

    if key_insight:
        st.info(f"**Key Insight:** {key_insight}")

    # Export ZIP button
    run_id = _ss_get("run_id")
    if run_id:
        try:
            zip_bytes = export_zip(run_id)
            st.download_button(
                "Download run (.zip)",
                zip_bytes,
                file_name=f"{run_id}.zip",
                mime="application/zip",
            )
        except Exception:
            pass

    st.divider()

    # --- 7 tabs ---
    tab_overview, tab_seg, tab_design, tab_quality, tab_recs, tab_report, tab_raw = st.tabs(
        ["Overview", "Segments", "Survey Design", "Quality", "Recommendations", "Report", "Raw Data"]
    )

    # =================== Tab 1: Overview ===================
    with tab_overview:
        st.subheader("Overview")

        seg_labels = [s.name for s in segments]
        seg_weights = [s.weight for s in segments]

        col1, col2 = st.columns(2)
        with col1:
            fig_pie = plotly_pie(seg_labels, seg_weights, title="Segment Population Weights")
            st.plotly_chart(fig_pie, width="stretch")

        # Find first likert question for quick bar
        first_likert = next((q for q in questions if q.type == "likert5" and q.condition == "neutral"), None)
        if first_likert:
            vals = []
            for sr in output.segment_results:
                stats = sr.question_summaries.get(first_likert.id)
                vals.append(stats["mean"] if stats else 0)
            with col2:
                fig = plotly_segment_bar(
                    seg_labels, vals,
                    title=f"Q: {first_likert.text[:60]}...",
                    y_label="Mean (1–5)",
                    vmin=1, vmax=5,
                )
                st.plotly_chart(fig, width="stretch")

        # SDB pair chart
        anon_q = next((q for q in questions if q.id.endswith("_anon")), None)
        named_q = next((q for q in questions if q.id.endswith("_named")), None)
        heatmap_col = None
        if anon_q and named_q:
            anon_vals = []
            named_vals = []
            for sr in output.segment_results:
                a = sr.question_summaries.get(anon_q.id)
                n = sr.question_summaries.get(named_q.id)
                anon_vals.append(a["mean"] if a else 0)
                named_vals.append(n["mean"] if n else 0)
            col3, col4 = st.columns(2)
            with col3:
                fig_sdb = plotly_grouped_bar(
                    seg_labels, anon_vals, named_vals,
                    title="Social Desirability Bias: Anon vs Named"
                )
                st.plotly_chart(fig_sdb, width="stretch")
            heatmap_col = col4

        # Multi-select heatmap
        ms_q = next((q for q in questions if q.type == "multi_select"), None)
        if ms_q and ms_q.options:
            opts = ms_q.options
            matrix = []
            for opt in opts:
                row = []
                for sr in output.segment_results:
                    stats = sr.question_summaries.get(ms_q.id)
                    if stats and "rates" in stats:
                        row.append(stats["rates"].get(opt, 0))
                    else:
                        row.append(None)
                matrix.append(row)
            if heatmap_col is None:
                _, heatmap_col = st.columns(2)
            with heatmap_col:
                fig_hm = plotly_heatmap(
                    opts, seg_labels, matrix,
                    title=f"Multi-select: {ms_q.text[:50]}..."
                )
                st.plotly_chart(fig_hm, width="stretch")

    # =================== Tab 2: Segments ===================
    with tab_seg:
        st.subheader("Audience Segments")

        for i, (seg, sr) in enumerate(zip(segments, output.segment_results)):
            color = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#b07aa1"][i % 6]
            with st.container(border=True):
                st.markdown(f"### {seg.name}")
                col_w, col_r = st.columns([1, 3])
                with col_w:
                    st.metric("Weight", f"{seg.weight:.0%}")
                with col_r:
                    st.caption(seg.rationale)

                # Per-question charts for this segment
                for q in questions:
                    if q.type == "open":
                        continue
                    stats = sr.question_summaries.get(q.id)
                    if not stats:
                        continue
                    label = f"{q.id}: {q.text[:60]}..."
                    if q.type == "likert5":
                        st.caption(label)
                        st.progress((stats["mean"] - 1) / 4, text=f"Mean: {stats['mean']}/5")
                    elif q.type == "binary":
                        st.caption(label)
                        st.progress(stats["pct_yes"] / 100, text=f"{stats['pct_yes']}% Yes")
                    elif q.type == "wtp":
                        st.caption(label)
                        st.metric("Mean WTP", f"NT${stats['mean']:.0f}")
                    elif q.type == "multi_select" and "rates" in stats:
                        st.caption(label)
                        top = sorted(stats["rates"].items(), key=lambda x: -x[1])[:3]
                        for opt, pct in top:
                            st.text(f"  {opt}: {pct:.1f}%")

                if sr.open_themes:
                    with st.expander("Open-ended responses"):
                        for t in sr.open_themes:
                            st.markdown(f"> {t}")

    # =================== Tab 3: Survey Design ===================
    with tab_design:
        st.subheader("Survey Design")
        st.caption("Generated by Agent 1 based on your input and clarifications.")

        for q in questions:
            badge_text, bg, fg = TYPE_BADGE_CSS.get(q.type, (q.type, "#ccc", "#333"))
            cond_tag = f" [{q.condition}]" if q.condition != "neutral" else ""
            with st.container(border=True):
                col_id, col_badge = st.columns([3, 1])
                with col_id:
                    st.markdown(f"**{q.id}**{cond_tag}")
                with col_badge:
                    st.markdown(
                        f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:4px;font-size:12px">'
                        f'{badge_text}</span>',
                        unsafe_allow_html=True,
                    )
                st.markdown(q.text)
                if q.scale_label:
                    st.caption(q.scale_label)
                if q.options:
                    st.caption("Options: " + " | ".join(q.options))

        st.subheader("Segment Personas")
        for seg in segments:
            with st.expander(f"{seg.name} (weight: {seg.weight:.0%})"):
                st.markdown(f"**Rationale:** {seg.rationale}")
                st.markdown(f"**Persona prompt:**\n\n> {seg.description}")

    # =================== Tab 4: Quality ===================
    with tab_quality:
        st.subheader("Run Quality")
        if not quality:
            st.caption("No quality report available.")
        else:
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Expected Responses", quality.get("expected_responses", "—"))
            q2.metric("Actual Responses", quality.get("actual_responses", "—"))
            q3.metric("Duplicate Cells", f"{quality.get('duplicate_cell_rate', 0) * 100:.0f}%")
            q4.metric("Flat Likert Cells", f"{quality.get('all_same_likert_rate', 0) * 100:.0f}%")

            warnings = quality.get("warnings", [])
            if warnings:
                for warning in warnings:
                    st.warning(warning)
            else:
                st.success("No major quality warnings detected.")

            detail_rows = []
            for item in quality.get("missing_cells", []):
                detail_rows.append({"type": "missing", **item})
            for item in quality.get("duplicate_cells", [])[:25]:
                detail_rows.append({"type": "duplicate", **item})
            for item in quality.get("all_same_likert_cells", [])[:25]:
                detail_rows.append({"type": "flat_likert", **item})
            for item in quality.get("length_finished_cells", [])[:25]:
                detail_rows.append({"type": "max_tokens", **item})
            for item in quality.get("incomplete_open_cells", [])[:25]:
                detail_rows.append({"type": "incomplete_open", **item})
            for item in quality.get("short_ssr_cells", [])[:25]:
                detail_rows.append({"type": "short_ssr", **item})
            if detail_rows:
                st.dataframe(pd.DataFrame(detail_rows), width="stretch", hide_index=True)

    # =================== Tab 5: Recommendations ===================
    with tab_recs:
        st.subheader("Strategic Recommendations")

        if output.target_segment:
            st.success(f"**Highest-receptivity segment:** {output.target_segment}")

        st.markdown("---")

        for i, rec in enumerate(output.recommendations, 1):
            st.markdown(
                f'<div style="border-left:4px solid #10B981;padding:8px 16px;margin-bottom:8px;background:#f0fdf4">'
                f'<b>{i}.</b> {rec}</div>',
                unsafe_allow_html=True,
            )

        if output.risk_flags:
            st.subheader("Risk Flags")
            for flag in output.risk_flags:
                st.markdown(
                    f'<div style="border-left:4px solid #F59E0B;padding:8px 16px;margin-bottom:8px;background:#fffbeb">'
                    f'{flag}</div>',
                    unsafe_allow_html=True,
                )

    # =================== Tab 6: Report ===================
    with tab_report:
        st.subheader("Report Mode")
        report_md = _build_report_markdown(output, segments, questions, quality)
        st.download_button(
            "Download report markdown",
            report_md.encode("utf-8"),
            file_name=f"{_ss_get('run_id') or 'prism'}_report.md",
            mime="text/markdown",
        )
        st.markdown(report_md)

    # =================== Tab 7: Raw Data ===================
    with tab_raw:
        st.subheader("Raw Simulated Responses")

        if responses:
            rows = [
                {
                    "Segment": r.segment_name,
                    "Question": r.question_id,
                    "Parsed Value": str(r.parsed_value),
                    "Raw Response": r.raw_response[:150],
                }
                for r in responses
            ]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

            df_full = pd.DataFrame([
                {
                    "segment": r.segment_name,
                    "question_id": r.question_id,
                    "parsed_value": str(r.parsed_value),
                    "raw_response": r.raw_response,
                }
                for r in responses
            ])
            col_csv, col_json = st.columns(2)
            with col_csv:
                st.download_button(
                    "Download CSV",
                    df_full.to_csv(index=False).encode(),
                    "prism_responses.csv",
                    "text/csv",
                )
            with col_json:
                st.download_button(
                    "Download JSON",
                    df_full.to_json(orient="records", force_ascii=False).encode(),
                    "prism_responses.json",
                    "application/json",
                )
        else:
            st.caption("Responses not available in this session (loaded from manifest).")

        # Agent 2 JSON
        if output:
            with st.expander("Agent 2 output (JSON)"):
                st.json({
                    "overall_summary": output.overall_summary,
                    "recommendations": output.recommendations,
                    "risk_flags": output.risk_flags,
                    "target_segment": output.target_segment,
                })


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

render_sidebar()

phase = _ss_get("phase", "setup")

if phase == "setup":
    page_setup()
elif phase == "clarify":
    page_clarify()
elif phase == "preview":
    page_preview()
elif phase == "run":
    page_run()
elif phase == "results":
    page_results()
else:
    page_setup()
