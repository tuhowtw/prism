"""
Prism — Demo Web UI
=========================
Streamlit app for the automated LLM market research pipeline.

Run with:  streamlit run prism_app.py
"""
from __future__ import annotations

import os
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from prism_engine import (
    AnalysisOutput,
    Segment,
    SurveyQuestion,
    run_agent1,
    run_agent2,
    run_simulation,
    _aggregate_responses,
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

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🔬 Prism")
    st.caption("Automated Market Research via Multi-Agent LLMs")
    st.divider()

    st.subheader("Simulation Settings")
    responses_per_cell = st.slider(
        "Responses per segment × question",
        min_value=3,
        max_value=30,
        value=8,
        help="More responses → more stable estimates, higher cost and time.",
    )
    st.caption(
        f"Total API calls: segments × 5 questions × {responses_per_cell} = "
        f"estimated {4 * 5 * responses_per_cell}–{5 * 5 * responses_per_cell} calls"
    )

    st.divider()
    st.subheader("About")
    st.markdown(
        """
**Pipeline:**
1. **Agent 1** — Identifies target segments, assigns weights, designs survey
2. **Simulation** — Parallel Claude API calls with persona injection
3. **Agent 2** — Aggregates results and produces strategy recommendations

**Reference:** Brand, Israeli & Ngwe (2023) — *Using GPT for Market Research*, MSI Working Paper 23-131
        """
    )

# ---------------------------------------------------------------------------
# Example inputs
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

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.title("Prism")
st.markdown(
    "Enter a product concept or policy proposal below. The system will simulate "
    "how different stakeholder groups perceive and respond to it — automatically."
)

# Input section
col_input, col_example = st.columns([3, 1])

with col_example:
    st.markdown("**Try an example:**")
    for label in EXAMPLES:
        if st.button(label, use_container_width=True):
            st.session_state["input_text"] = EXAMPLES[label]

with col_input:
    input_text = st.text_area(
        "Product / Policy Description",
        value=st.session_state.get("input_text", ""),
        height=160,
        placeholder=(
            "Describe your product or policy in plain language. "
            "Include target audience, key features, pricing, and context."
        ),
    )
    if input_text:
        st.session_state["input_text"] = input_text

run_btn = st.button("Run Full Pipeline", type="primary", disabled=not input_text)

# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------

if run_btn and input_text:
    # Clear previous results
    for key in ["segments", "questions", "responses", "seg_results", "output"]:
        st.session_state.pop(key, None)

    st.divider()

    # --- Stage 1: Agent 1 ---
    with st.status("Agent 1: Analyzing audience and designing survey...", expanded=True) as status:
        st.write("Identifying target demographic segments...")
        st.write("Assigning population weights...")
        st.write("Designing survey questions...")
        try:
            segments, questions = run_agent1(input_text)
            st.session_state["segments"] = segments
            st.session_state["questions"] = questions
            status.update(
                label=f"Agent 1 complete — {len(segments)} segments, {len(questions)} questions",
                state="complete",
            )
        except Exception as e:
            status.update(label=f"Agent 1 failed: {e}", state="error")
            st.stop()

    # --- Stage 2: Simulation ---
    with st.status("Simulation: Running synthetic respondents...", expanded=True) as status:
        total_calls = len(segments) * len(questions) * responses_per_cell
        st.write(f"Dispatching {total_calls} parallel API calls...")
        st.write(f"Temperature=1.0 for response heterogeneity")
        try:
            responses = run_simulation(segments, questions, responses_per_cell=responses_per_cell)
            st.session_state["responses"] = responses
            status.update(
                label=f"Simulation complete — {len(responses)} responses collected",
                state="complete",
            )
        except Exception as e:
            status.update(label=f"Simulation failed: {e}", state="error")
            st.stop()

    # --- Stage 3: Aggregation + Agent 2 ---
    with st.status("Agent 2: Aggregating results and generating recommendations...", expanded=True) as status:
        st.write("Computing weighted segment statistics...")
        st.write("Synthesizing strategic recommendations...")
        try:
            seg_results = _aggregate_responses(responses, segments, questions)
            output = run_agent2(seg_results, questions, input_text)
            st.session_state["seg_results"] = seg_results
            st.session_state["output"] = output
            status.update(label="Analysis complete", state="complete")
        except Exception as e:
            status.update(label=f"Agent 2 failed: {e}", state="error")
            st.stop()

# ---------------------------------------------------------------------------
# Results display
# ---------------------------------------------------------------------------

if "output" in st.session_state:
    output: AnalysisOutput = st.session_state["output"]
    segments: list[Segment] = st.session_state["segments"]
    questions: list[SurveyQuestion] = st.session_state["questions"]

    st.divider()

    # --- Top-level metrics ---
    overall = output.overall_summary
    reception = overall.get("weighted_reception_score", "—")
    key_insight = overall.get("key_insight", "")

    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Overall Reception Score",
        f"{reception}/5" if isinstance(reception, (int, float)) else reception,
        help="Weighted average Likert score across all segments",
    )
    m2.metric("Target Segment", output.target_segment or "—")
    m3.metric(
        "Responses Collected",
        len(st.session_state.get("responses", [])),
    )

    if key_insight:
        st.info(f"**Key Insight:** {key_insight}")

    st.divider()

    # --- Tabs ---
    tab_seg, tab_questions, tab_recs, tab_raw = st.tabs(
        ["Segment Breakdown", "Survey Design", "Recommendations", "Raw Data"]
    )

    # ---- Tab: Segment Breakdown ----
    with tab_seg:
        st.subheader("Audience Segments")

        seg_rows = []
        for seg in segments:
            seg_rows.append({
                "Segment": seg.name,
                "Weight": f"{seg.weight:.0%}",
                "Rationale": seg.rationale,
            })
        st.dataframe(
            pd.DataFrame(seg_rows),
            use_container_width=True,
            hide_index=True,
        )

        # Segment weight pie
        pie_df = pd.DataFrame({"Segment": [s.name for s in segments], "Weight": [s.weight for s in segments]})
        fig_pie = px.pie(
            pie_df,
            names="Segment",
            values="Weight",
            title="Segment Population Weights",
            hole=0.4,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

        # Per-question bar charts
        st.subheader("Responses by Segment")

        for q in questions:
            if q.type == "open":
                continue

            chart_data = []
            for sr in output.segment_results:
                stats = sr.question_summaries.get(q.id)
                if not stats:
                    continue
                if q.type == "likert5":
                    chart_data.append({"Segment": sr.segment.name, "Value": stats["mean"], "Metric": "Mean rating (1–5)"})
                elif q.type == "binary":
                    chart_data.append({"Segment": sr.segment.name, "Value": stats["pct_yes"], "Metric": "% Yes"})
                elif q.type == "wtp":
                    chart_data.append({"Segment": sr.segment.name, "Value": stats["mean"], "Metric": "Mean WTP (NT$)"})

            if not chart_data:
                continue

            df_chart = pd.DataFrame(chart_data)
            y_label = df_chart["Metric"].iloc[0]

            fig_bar = px.bar(
                df_chart,
                x="Segment",
                y="Value",
                color="Segment",
                title=f"Q: {q.text[:80]}{'...' if len(q.text) > 80 else ''}",
                labels={"Value": y_label},
                text_auto=".2f",
            )
            if q.type == "likert5":
                fig_bar.update_yaxes(range=[1, 5])
            elif q.type == "binary":
                fig_bar.update_yaxes(range=[0, 100])
            fig_bar.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig_bar, use_container_width=True)

        # Open-ended samples
        open_qs = [q for q in questions if q.type == "open"]
        if open_qs:
            st.subheader("Open-Ended Response Samples")
            for sr in output.segment_results:
                if sr.open_themes:
                    with st.expander(f"**{sr.segment.name}** — sample responses"):
                        for t in sr.open_themes:
                            st.markdown(f"> {t}")

    # ---- Tab: Survey Design ----
    with tab_questions:
        st.subheader("Agent 1 — Survey Design Output")
        st.caption("These questions were automatically generated based on your input.")

        for q in questions:
            type_badge = {
                "likert5": "⭐ Likert 1–5",
                "binary": "✅ Yes/No",
                "wtp": "💰 Willingness to Pay",
                "open": "💬 Open-Ended",
            }.get(q.type, q.type)
            with st.container(border=True):
                st.markdown(f"**{q.id.upper()}** &nbsp; `{type_badge}`")
                st.markdown(q.text)
                if q.scale_label:
                    st.caption(q.scale_label)

        st.subheader("Segment Personas")
        st.caption("These descriptions are injected as the system prompt for each simulated respondent.")
        for seg in segments:
            with st.expander(f"**{seg.name}** (weight: {seg.weight:.0%})"):
                st.markdown(f"**Persona prompt:**\n\n> {seg.description}")

    # ---- Tab: Recommendations ----
    with tab_recs:
        col_rec, col_risk = st.columns(2)

        with col_rec:
            st.subheader("Strategic Recommendations")
            for i, rec in enumerate(output.recommendations, 1):
                st.markdown(f"**{i}.** {rec}")

        with col_risk:
            st.subheader("Risk Flags")
            for flag in output.risk_flags:
                st.warning(flag)

        if output.target_segment:
            st.success(
                f"**Highest-receptivity segment:** {output.target_segment} — "
                f"prioritize marketing and pilot rollout toward this group."
            )

    # ---- Tab: Raw Data ----
    with tab_raw:
        responses = st.session_state.get("responses", [])
        if responses:
            st.subheader(f"All Simulated Responses ({len(responses)} total)")
            rows = [
                {
                    "Segment": r.segment_name,
                    "Question": r.question_id,
                    "Parsed Value": r.parsed_value,
                    "Raw Response": r.raw_response[:120],
                }
                for r in responses
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            # Download
            df_full = pd.DataFrame([
                {
                    "segment": r.segment_name,
                    "question_id": r.question_id,
                    "parsed_value": r.parsed_value,
                    "raw_response": r.raw_response,
                }
                for r in responses
            ])
            st.download_button(
                "Download CSV",
                df_full.to_csv(index=False).encode(),
                "prism_responses.csv",
                "text/csv",
            )

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

elif not run_btn:
    st.divider()
    st.markdown(
        """
        ### How it works

        | Step | Agent | What happens |
        |---|---|---|
        | 1 | **Audience Analyst** | Reads your description, identifies 3–5 stakeholder segments with population weights, designs 5 survey questions |
        | 2 | **Simulation Layer** | For each segment × question, dispatches hundreds of parallel Claude API calls, each conditioned on a vivid demographic persona |
        | 3 | **Strategist** | Aggregates responses with segment weights, computes statistics, and generates actionable product/marketing recommendations |

        **Grounded in:** Brand, Israeli & Ngwe (2023) — *Using GPT for Market Research*
        **Architecture inspired by:** MiroFish multi-agent simulation engine
        """
    )
