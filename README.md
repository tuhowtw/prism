# Prism

**AI-powered multi-agent market research simulator** — takes a plain-language policy or product description and produces simulated survey responses from diverse stakeholder personas, SDB (Social Desirability Bias) gap analysis, and strategic recommendations.

Built as part of Economic Policy Analysis (2026) at NTU. Research domains: Taiwan fertility policy and digital piracy implicit preferences.

---

## How It Works

```
User Input (policy / product description)
       ↓
Agent 1 — Phase A: Clarifying questions (geography, segments, sensitivity…)
       ↓
Agent 1 — Phase B: Proposes 3–5 demographic segments + 12–15 survey questions
       ↓
Simulation: N parallel LiteLLM calls per segment × question (temp=1.0)
       ↓
SSR Scoring: free-text responses → Likert pmf via embedding cosine similarity
       ↓
Aggregation: mean, SD, SDB gap (anon − named), multi-select rates, WTP
       ↓
Agent 2: Strategic recommendations + target segment + risk flags
       ↓
Output: interactive SVG HTML report + SQLite DB + manifest JSON
```

**SDB pair design:** questions with `_anon` / `_named` id suffixes are automatically paired. Condition framing (anonymous / named / neutral) is injected per question as a system prompt prefix during simulation.

---

## Quick Start

### Prerequisites

- Python 3.11+
- API keys: Gemini (billing enabled) and/or Anthropic — see [API Setup](#api-setup)

```bash
git clone https://github.com/tuhowtw/prism.git
cd prism
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your API keys
```

### Run the Web UI

```bash
streamlit run prism_app.py
```

Navigate: **Setup → Clarify → Preview → Run → Results**

### CLI Tests

```bash
# Quick test — fertility policy, N=5 (~60s)
python prism_cli_test.py

# Smoke test — piracy SDB, N=20 (~2–3 min)
python prism_smoke_piracy.py

# SSR unit test
python prism_ssr_test.py
```

### Generate Report from a Past Run

```bash
python prism_report.py runs/20260522_173045_n20.jsonl
# Writes: runs/20260522_173045_n20.html  +  .db
```

---

## Project Structure

```
prism/
├── prism_engine.py        # Core pipeline — Agent 1/2, simulation, SSR scoring
├── prism_report.py        # SQLite + SVG-embedded HTML report generator
├── prism_app.py           # Streamlit 4-phase web UI
├── prism_session.py       # Manifest I/O, run listing, zip export/import
├── prism_viz.py           # SVG generators (report) + Plotly builders (app)
├── prism_smoke_piracy.py  # End-to-end smoke test — piracy SDB study
├── prism_cli_test.py      # CLI smoke test — fertility policy
├── prism_ssr_test.py      # Unit test for SSR embedding scoring
├── prism_demo.html        # Static HTML prototype (visual reference)
├── requirements.txt
├── runs/                  # Gitignored — timestamped run outputs
│   └── {run_id}/
│       ├── manifest.json
│       ├── {run_id}.jsonl
│       ├── {run_id}_report.json
│       ├── {run_id}.html
│       └── {run_id}.db
└── .env                   # Gitignored — API keys + model config
```

**Legacy / supplementary files** (earlier MVPs):

| File | Purpose |
|---|---|
| `macro_simulation_demo.py` | Consumption-savings dynamic optimization |
| `mvp_fertility_simulator.py` | Taiwan fertility data aggregator + RAG demo |
| `mvp_cbc_watcher.py` | Taiwan Central Bank FX rate scraper |
| `app.py` / `app_fertility.py` | Streamlit apps for the above MVPs |

---

## API Setup

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
PRISM_ALLOW_ENV_KEY=true

# Optional model overrides (these are the defaults):
PRISM_AGENT_MODEL=claude-sonnet-4-6
PRISM_SIM_MODEL=gemini/gemini-2.0-flash
PRISM_EMBED_MODEL=text-embedding-3-small
```

- **Gemini billing must be enabled** — the free tier (20 RPD) is too slow for full runs
- Recommended: set a spending cap (e.g. NT$150) on Google AI Studio

**Cost estimates:**
- Smoke test (20 responses/cell, 4 seg × 13 Q): ~$0.10–0.30
- Full production run (300 responses/cell): ~$5–15

---

## Key Concepts

**Segments** — 3–5 demographic personas (e.g. "Urban White-Collar 25–35", "Rural Blue-Collar 45–55"), each with a `weight` reflecting population share. Agent 1 generates these from the user's input and clarifying answers.

**Survey Questions** — typed as `likert5`, `binary`, `wtp`, `open`, or `multi_select`. Each has an optional `condition` (`neutral` / `anonymous` / `named`) for SDB pairing.

**SSR (Semantic Similarity Rating)** — maps a free-text simulation response to a Likert pmf via cosine similarity against embedded anchor phrases. Based on Maier et al. (2025). Returns a 5-element distribution and expected value ∈ [1, 5].

**SDB Gap** — `anon_mean − named_mean` per question. Positive gap = respondents express higher agreement when anonymous, suggesting social desirability suppression under named conditions.

---

## Report Features

The generated `.html` report is fully self-contained (no CDN dependencies):

- Sticky sidebar with TOC + segment/question filter dropdowns + keyword search
- Per-question chart grid: vertical bars, mini histograms, SSR pmf bars, heatmaps, SDB gap charts
- Collapsible summary tables and raw response tables
- Smooth scroll navigation

---

## Architecture Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| LLM framework | LiteLLM | Model-agnostic — Claude, Gemini, others from one API |
| Agent 1 two-phase | Clarify → Propose | Captures intent before survey design is locked in |
| SSR scoring | Embedding cosine similarity | Maps free-text to Likert without forcing structured output |
| SDB detection | `_anon` / `_named` id suffixes | Auto-pairing; visible in output without extra config |
| Simulation temperature | 1.0 | Maximises response heterogeneity |
| Concurrency | asyncio, max 3–5 parallel | Balances speed vs. rate limits |
| Report format | Self-contained HTML + SQLite | Offline-ready; no server needed for sharing |

---

## Evaluation Metrics

1. **SDB gap magnitude** — difference in mean response between anonymous and named conditions
2. **Cross-segment perception divergence** — variance in means across demographic segments
3. **SSR pmf calibration** — embedding-based Likert distribution vs. ground-truth survey benchmarks
4. **Agent 2 recommendation precision** — alignment of target segment with real-world outcomes (TBD)

---

## Authors

涂皓 (TU HOW) + Claude — Economic Policy Analysis, NTU, 2026
