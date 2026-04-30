from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from mvp_fertility_simulator import save_snapshot


st.set_page_config(page_title="East Asia Fertility Policy Simulator MVP", layout="wide")


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z]{3,}", text.lower()))


def retrieve_docs(query: str, docs: list[dict[str, str]], k: int = 3) -> list[dict[str, str]]:
    q = _tokenize(query)
    if not q:
        return docs[:k]

    scored: list[tuple[int, dict[str, str]]] = []
    for doc in docs:
        dt = _tokenize(doc.get("title", "") + " " + doc.get("text", ""))
        score = len(q.intersection(dt))
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for score, doc in scored[:k] if score > 0] or docs[:k]


def build_llm_prompt(query: str, top_docs: list[dict[str, str]], panel_df: pd.DataFrame) -> str:
    latest = (
        panel_df.sort_values("year")
        .dropna(subset=["tfr_births_per_woman"])
        .groupby("country", as_index=False)
        .tail(1)[["country", "country_name", "year", "tfr_births_per_woman"]]
    )

    stats_lines = [
        f"- {r.country} ({r.country_name}), year={int(r.year)}, TFR={float(r.tfr_births_per_woman):.3f}"
        for r in latest.itertuples(index=False)
    ]

    ctx_lines = []
    for i, doc in enumerate(top_docs, start=1):
        ctx_lines.append(f"[Doc {i}] {doc['title']}\nURL: {doc['url']}\nSnippet: {doc['text'][:700]}")

    return (
        "You are a policy economist assistant. Use only the provided context and data.\n\n"
        "Task:\n"
        f"{query}\n\n"
        "Latest Fertility Data:\n"
        + "\n".join(stats_lines)
        + "\n\nRetrieved Context:\n"
        + "\n\n".join(ctx_lines)
        + "\n\nOutput format:\n"
        "1) Key diagnosis by country\n"
        "2) Policy package with expected effect channels\n"
        "3) Risks and caveats\n"
        "4) What new data to collect next"
    )


def heuristic_llm_answer(query: str, panel_df: pd.DataFrame, policy_intensity: dict[str, int]) -> str:
    latest = (
        panel_df.sort_values("year")
        .dropna(subset=["tfr_births_per_woman"])
        .groupby("country", as_index=False)
        .tail(1)[["country", "country_name", "year", "tfr_births_per_woman"]]
    )

    lift = (
        0.0008 * policy_intensity["childcare_subsidy"]
        + 0.0007 * policy_intensity["housing_support"]
        + 0.0010 * policy_intensity["parental_leave"]
        + 0.0009 * policy_intensity["childcare_supply"]
    )

    lines = [
        f"Heuristic response for query: {query}",
        "",
        "Projected TFR under selected policy package:",
    ]
    for row in latest.itertuples(index=False):
        base = float(row.tfr_births_per_woman)
        projected = max(0.2, base + lift)
        lines.append(
            f"- {row.country} ({row.country_name}) baseline {base:.3f} -> projected {projected:.3f} "
            f"(year {int(row.year)} baseline)"
        )

    lines.extend(
        [
            "",
            "Interpretation:",
            "- Childcare availability and leave support generally have the strongest direct fertility-channel effect.",
            "- Housing support improves family formation incentives but interacts with local price dynamics.",
            "- Validate impacts with lag structure (1-3 years) and subgroup heterogeneity before policy scaling.",
        ]
    )
    return "\n".join(lines)


st.title("East Asia Fertility Policy Simulator MVP")
st.caption("Taiwan (RIS Table 11) + Japan/Korea (World Bank API) with RAG-style policy retrieval")

left, right = st.columns([1, 3])
with left:
    refresh = st.button("Refresh Scraped Data", type="primary")

if refresh:
    with st.spinner("Scraping data and rebuilding snapshot..."):
        paths = save_snapshot(output_dir="data")
else:
    snap = Path("data/fertility_mvp_snapshot.json")
    if not snap.exists():
        with st.spinner("No fertility snapshot yet. Running first scrape..."):
            paths = save_snapshot(output_dir="data")
    else:
        paths = {
            "snapshot_json": snap,
            "panel_csv": Path("data/fertility_east_asia_panel.csv"),
            "taiwan_csv": Path("data/fertility_taiwan_table11_yearly.csv"),
            "rag_docs_json": Path("data/fertility_rag_docs.json"),
        }

payload = json.loads(Path(paths["snapshot_json"]).read_text(encoding="utf-8"))
panel_df = pd.DataFrame(payload.get("east_asia_panel", []))
tw_df = pd.DataFrame(payload.get("taiwan_table11_yearly", []))
rag_docs = payload.get("rag_docs", [])

summary = payload.get("summary", {})
c1, c2, c3 = st.columns(3)
c1.metric("Panel records", summary.get("records_panel", 0))
c2.metric("Countries", len(summary.get("countries", [])))
c3.metric("RAG docs", summary.get("rag_docs_count", 0))

tab1, tab2, tab3 = st.tabs(["Data", "Policy Simulator", "LLM/RAG Demo"])

with tab1:
    if not panel_df.empty:
        panel_df["year"] = panel_df["year"].astype(int)
        fig = px.line(
            panel_df,
            x="year",
            y="tfr_births_per_woman",
            color="country_name",
            markers=True,
            title="Total Fertility Rate (Births per Woman)",
        )
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Taiwan Detailed Series (from RIS Table 11)")
        st.dataframe(
            tw_df[[
                "year",
                "crude_birth_rate_per_thousand_population",
                "general_fertility_rate_per_thousand_women",
                "tfr_births_per_woman",
            ]].sort_values("year", ascending=False),
            use_container_width=True,
        )

with tab2:
    st.write("Adjust policy intensity and view heuristic TFR shift.")
    p1, p2 = st.columns(2)
    with p1:
        childcare_subsidy = st.slider("Childcare subsidy intensity", 0, 100, 45)
        housing_support = st.slider("Housing support intensity", 0, 100, 35)
    with p2:
        parental_leave = st.slider("Parental leave generosity", 0, 100, 50)
        childcare_supply = st.slider("Childcare supply expansion", 0, 100, 40)

    policy = {
        "childcare_subsidy": childcare_subsidy,
        "housing_support": housing_support,
        "parental_leave": parental_leave,
        "childcare_supply": childcare_supply,
    }

    latest = (
        panel_df.sort_values("year")
        .dropna(subset=["tfr_births_per_woman"])
        .groupby("country", as_index=False)
        .tail(1)
    )
    lift = (
        0.0008 * childcare_subsidy
        + 0.0007 * housing_support
        + 0.0010 * parental_leave
        + 0.0009 * childcare_supply
    )
    sim_df = latest[["country", "country_name", "year", "tfr_births_per_woman"]].copy()
    sim_df["projected_tfr"] = (sim_df["tfr_births_per_woman"] + lift).clip(lower=0.2)

    fig2 = px.bar(
        sim_df,
        x="country_name",
        y=["tfr_births_per_woman", "projected_tfr"],
        barmode="group",
        title="Baseline vs Simulated TFR",
        labels={"value": "Births per woman", "variable": "Series"},
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(sim_df, use_container_width=True)

with tab3:
    st.write("This section shows how RAG and an LLM would be used in the project.")
    query = st.text_input(
        "Policy question",
        value="Design a 3-year fertility support package for Taiwan, Japan, and Korea with trade-offs.",
    )

    top_docs = retrieve_docs(query, rag_docs, k=3)
    st.markdown("**Step 1: Retrieval (RAG)**")
    for idx, doc in enumerate(top_docs, start=1):
        st.markdown(f"{idx}. [{doc['title']}]({doc['url']})")
        st.caption(doc["text"][:260] + "...")

    llm_prompt = build_llm_prompt(query, top_docs, panel_df)
    st.markdown("**Step 2: LLM Prompt Built from Retrieved Context + Data**")
    st.code(llm_prompt, language="markdown")

    st.markdown("**Step 3: Demo Answer (Heuristic stand-in for LLM output)**")
    st.code(heuristic_llm_answer(query, panel_df, policy), language="text")

    st.info(
        "To connect a real LLM, send the generated prompt to your model API (OpenAI, Azure OpenAI, Claude, or local model)."
    )
