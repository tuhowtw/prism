# Econ Policy Analysis — AI Project

## Course Context

**Course:** Economic Policy Analysis (2026)
**Format:** LLMs + prompt engineering + agentic workflows applied to core econ policy topics (inflation, welfare, dynamic optimization, optimal taxation). Assessment is a team AI project with a mid-term progress presentation.

**Syllabus pillars:**
1. AI Application — LLMs, prompt engineering, vibe coding, multi-agent systems
2. Conceptual (in-class) — beauty contest & investment, inflation & interest rates, matching & optimal stopping
3. Theoretical (online) — inequality & welfare, dynamic programming, optimal income taxation

## Our Project Direction

**Project name:** Prism
**Core idea:** Use LLMs to simulate how different stakeholder groups perceive and react to economic policies and products.

This sits at the intersection of:
- **Beauty contest dynamics** — agents form beliefs about what others believe
- **Prompt engineering for policy** — crafting LLM personas to proxy real-world agents
- **Multi-agent simulation** — running ensembles of LLM "respondents" to surface distributional perception gaps

**Policy domains:** Taiwan fertility policy (NT$200k subsidy demo) + **piracy SDB study** (active research run)

## What We're Building Together

- [x] Project proposal — `proposal.md` / `proposal.pdf`
- [x] Presentation slides — `prism_slides.pptx`
- [x] Working demo — CLI smoke test on piracy SDB study (N=20, full pipeline verified)
- [x] Extended engine — multi-select, anon/named condition framing, SDB gap aggregation
- [x] SSR (Semantic Similarity Rating) — embedding-based free-text → Likert pmf mapping
- [x] SVG report — offline HTML with bar charts, heatmap, histograms, TOC sidebar
- [x] Streamlit UI — 4-phase navigation, session persistence, zip export/import
- [x] Session management — manifest JSON, run listing, zip export/import (`prism_session.py`)
- [ ] Mid-term progress slides
- [ ] Streamlit UI polish to fully expose extended engine features

## Key Files

| File | Purpose |
|---|---|
| `prism_engine.py` | Core pipeline — Agent 1 (2-phase), simulation, Agent 2, SSR scoring |
| `prism_report.py` | Generates SQLite DB + SVG-visualized HTML report from any run |
| `prism_app.py` | Streamlit web UI — 4-phase navigation + session persistence |
| `prism_session.py` | Manifest I/O, run listing, zip export/import helpers |
| `prism_viz.py` | Shared SVG generators (for report) + Plotly builders (for app) |
| `prism_smoke_piracy.py` | End-to-end smoke test on piracy SDB research question (N=20) |
| `prism_cli_test.py` | Original CLI test — fertility policy input (N=5) |
| `prism_ssr_test.py` | Unit test for SSR embedding-based scoring |
| `prism_demo.html` | Static HTML prototype (visual reference only) |
| `runs/` | Timestamped run outputs — `.jsonl`, `_report.json`, `.html`, `.db` (gitignored) |
| `.env` | API keys + model config (gitignored) |

### Supporting / Legacy Files

| File | Purpose |
|---|---|
| `macro_simulation_demo.py` | Dynamic optimization: consumption-savings Euler solver |
| `mvp_fertility_simulator.py` | Taiwan fertility data aggregator + RAG demo |
| `mvp_cbc_watcher.py` | Taiwan Central Bank FX rate scraper |
| `app.py` | Streamlit app for CBC watcher MVP |
| `app_fertility.py` | Streamlit app for fertility policy simulator |
| `macro_simulation_interactive.ipynb` | Jupyter notebook for macro model |
| `test_simulation.py` | Macro model unit test |

## Architecture

**Stack:** Python + LiteLLM + Streamlit + asyncio
**Model config (via `.env`):**
```
PRISM_AGENT_MODEL=claude-sonnet-4-6       # Agent 1 & 2 (default)
PRISM_SIM_MODEL=gemini/gemini-2.0-flash   # Bulk simulation (default)
PRISM_EMBED_MODEL=text-embedding-3-small  # SSR embeddings (default)
PRISM_ALLOW_ENV_KEY=true                  # Reads API key from .env when true
```
- Gemini API key with **billing enabled** (NT$150 cap set); free tier too rate-limited for full runs

**Full Pipeline:**
1. **Agent 1 Phase A** — `run_agent1_clarify()`: generates 2–5 adaptive clarifying questions covering geography, decision, segments, sensitivity, success_metric, constraints
2. **Agent 1 Phase B** — `run_agent1_propose()`: designs 3–5 demographic segments + 12–15 questions; enforces: ≥1 anon/named SDB pair, ≥1 multi_select, 1 open-ended
3. **Simulation** — `run_simulation_async()`: parallel LiteLLM calls at temperature=1.0; condition framing injected per question; max 3–5 concurrent; retry + rate-limit handling
4. **SSR Scoring** — `_ssr_score()`: maps free-text response → Likert pmf via embedding cosine similarity against anchor sets; pre-warms anchor cache before simulation
5. **Aggregation** — per-segment stats: mean, SD, % yes, mean WTP, multi-select rates, SDB gap (anon_mean − named_mean)
6. **Agent 2** — `run_agent2()`: strategic recommendations JSON with target segment, risk flags, opportunity summary

**Key Data Classes (prism_engine.py):**
- `Segment` — name, persona description, population weight, rationale
- `SurveyQuestion` — type (`likert5`/`binary`/`wtp`/`open`/`multi_select`), condition (`neutral`/`anonymous`/`named`), SSR anchor set, options list
- `ClarifyQuestion` — question text, answer type, choices
- `SimulatedResponse` — raw text + parsed value + SSR pmf
- `SegmentResult` — aggregated stats per segment per question
- `AnalysisOutput` — Agent 2 output (recommendations, risk flags, target segment)

**SDB Pair Detection:**
- Matched automatically by `_anon` / `_named` suffixes in question `id` field
- Condition framing injected as system prompt prefix during simulation
  - `anonymous`: "This response is collected fully anonymously..."
  - `named`: "Your real name and ID will be recorded..."
  - `neutral`: no framing

**Survey format:** Likert-5 primary, one `multi_select`, one anon/named SDB pair, one `wtp`, one `open`.

## prism_report.py — HTML Report Generation

**Workflow:** reads `runs/{timestamp}_n{N}.jsonl` → loads optional `_report.json` → creates SQLite → renders SVG charts → writes single-page HTML.

**SQLite tables:** `responses`, `segments`, `questions`

**Visualizations per question type:**
- `likert5`: vertical bar (segments) + mini histograms + SD labels + SSR pmf bar
- `binary`: 0–100% bars per segment
- `wtp`: NT$ bars per segment
- `multi_select`: heatmap (options × segments %)
- `open`: sample quotes per segment
- SDB pairs: grouped anon/named bars + horizontal SDB gap bar chart

**HTML features:** sticky sidebar with TOC + segment/question filter dropdowns + keyword search + collapsible data tables + smooth scroll.

## prism_app.py — Streamlit UI

**4-phase navigation:**
1. **Setup** — paste policy/product description or pick example
2. **Clarify** — answer Agent 1's clarifying questions (multi/single-select, text, number, skippable)
3. **Preview** — edit segments (name, weight, persona) + questions (text, type, condition); weight normalization
4. **Run** — threaded simulation with progress bar → auto-aggregation → Agent 2
5. **Results** — 5 tabs: Overview, Segments, Survey Design, Recommendations, Raw Data

**Sidebar:** API key validation, model/N slider, past run list, ZIP import.

**Session persistence:** `manifest.json` per run in `runs/{run_id}/`; list/reload past runs; export/import ZIP.

## prism_session.py — Session Management

- `make_run_id()` → `"20260522_173045_n8"` format
- `run_dir()` → creates `runs/{run_id}/` on demand
- `save_manifest()` / `load_manifest()` — atomic JSON I/O
- `list_runs()` — sorted list of all manifests, latest first
- `export_zip()` / `import_zip()` — full run folder as ZIP
- `segment_to_dict()` / `question_to_dict()` / `clarify_to_dict()` — serialization helpers

## prism_viz.py — Visualization Helpers

**SVG (for prism_report.py):** `svg_vbar`, `svg_grouped_vbar`, `svg_sdb_hbar`, `svg_histogram`, `svg_heatmap`, `_svg_pmf_dist`

**Plotly (for prism_app.py):** `plotly_segment_bar`, `plotly_grouped_bar`, `plotly_pie`, `plotly_heatmap`

**Color palette:** `SEG_COLORS = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#b07aa1"]`

## Run Output Structure

```
runs/
└── 20260522_173045_n20/
    ├── manifest.json                       # Full session state snapshot
    ├── 20260522_173045_n20.jsonl           # Raw responses (1 JSON per line)
    ├── 20260522_173045_n20_report.json     # Agent 2 output + segments + questions
    ├── 20260522_173045_n20.html            # Interactive SVG report (self-contained)
    └── 20260522_173045_n20.db             # SQLite: responses, segments, questions
```

All run outputs are gitignored — commit only source code, not generated data.

## Development Workflows

### Quick CLI Test (fertility policy, N=5, ~60s)
```bash
python prism_cli_test.py
```

### Smoke Test (piracy SDB, N=20, ~2–3 min)
```bash
python prism_smoke_piracy.py
```

### SSR Unit Test
```bash
python prism_ssr_test.py
```

### Web UI
```bash
streamlit run prism_app.py
# Then: Setup → Clarify → Preview → Run → Results
```

### Generate HTML Report from JSONL
```bash
python prism_report.py runs/20260522_173045_n20.jsonl
# Outputs: .html + .db in same directory
```

### Cost Estimates
- Smoke test (20/cell, 4 seg × 13 Q): ~$0.10–0.30 (Gemini)
- Full production run (300/cell): ~$5–15 (Gemini)

## Collaboration Notes

- Co-authoring: Claude drafts, 涂皓 (TU HOW) reviews and steers
- Keep proposal language precise but accessible — audience is economists, not ML engineers
- Slides: use `/slides` skill — compiles with XeLaTeX (needed for Chinese characters)
- All deliverables live in this directory

## Data & API Setup

- **Gemini API Key:** stored in `.env` as `GEMINI_API_KEY` (do not commit)
- **Anthropic API Key:** stored in `.env` as `ANTHROPIC_API_KEY` (do not commit)
- **Billing:** enabled on Google AI Studio project — free tier (20 RPD) too slow for full runs; NT$150 cap set
- **FRED API Key:** stored in `fred_prac/.claude/settings.json` as `FRED_API_KEY` env var

## Key Design Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| LLM framework | LiteLLM | Model-agnostic; supports Claude, Gemini, others from one API |
| Agent 1 two-phase | Clarify → Propose | Captures user intent before locking in survey design |
| SSR scoring | Embedding cosine similarity | Maps free-text to Likert without forcing structured output |
| SDB detection | `_anon`/`_named` id suffixes | Automatic pairing; visible in output without extra config |
| Simulation temperature | 1.0 | Maximizes response heterogeneity across simulated respondents |
| Concurrency | asyncio, max 3–5 parallel | Balances speed vs. rate limits |
| Report format | Self-contained HTML + SQLite | Offline-ready; no server needed for sharing |
| Validation approach | TBD — candidates: real survey benchmarks, expert review | |

## Rubric Alignment

The course evaluates on:
- Identifying an inefficiency or research gap
- AI system design (LLM, optional RAG, optional agent workflow)
- Demonstrated impact on: information asymmetry, transaction costs, market failure, or empirical gaps
- Measurable evaluation metrics (at least 3)

**Prism's metrics:** SDB gap magnitude, cross-segment perception divergence, SSR pmf calibration vs. ground truth, Agent 2 recommendation precision.
