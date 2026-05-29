---
title: "Prism — Collaborator Setup Guide"
author: "Prism Project Team"
date: "2026"
geometry: "margin=2.5cm"
fontsize: 11pt
colorlinks: true
---

# Prism — Collaborator Setup Guide

**Project:** Prism — AI-Powered Policy & Product Perception Simulator  
**Course:** Economic Policy Analysis (2026)  
**Team:** 涂皓 TU HOW + collaborator

---

## What Is Prism?

Prism uses large language models (LLMs) to simulate how different stakeholder groups perceive and react to economic policies or product proposals. It surfaces distributional perception gaps that traditional surveys miss.

**Core idea:** Instead of asking one LLM "what do people think?", Prism injects distinct persona prompts for each stakeholder group and runs *N* parallel simulated respondents per group. The results expose who supports a policy and who doesn't — before you spend real money on fieldwork.

**Current demo domain:** Taiwan fertility policy (NT$200k subsidy) + piracy social-desirability bias (SDB) study.

---

## Repository Overview

```
econ_policy/
├── prism_app.py          # Streamlit web UI (main entry point)
├── prism_engine.py       # Core pipeline — Agent 1, simulation, Agent 2
├── prism_session.py      # Run persistence, zip import/export
├── prism_viz.py          # SVG + Plotly chart helpers
├── prism_report.py       # Generates HTML report from a run
├── prism_smoke_piracy.py # CLI smoke test — piracy SDB study
├── prism_cli_test.py     # CLI smoke test — fertility policy
├── runs/                 # Timestamped run outputs (.jsonl, .json, .html, .db)
├── requirements.txt      # Python dependencies
└── .env                  # API keys (NOT committed — you must create this)
```

---

## Step 1: Prerequisites

- **Python 3.11+** — check with `python --version`
- **Git** — check with `git --version`
- **A Google AI Studio account** with a Gemini API key (billing enabled)
  - Free tier is rate-limited to 20 req/day — too slow for full runs
  - NT$150 cap is sufficient for development

---

## Step 2: Clone the Repository

```bash
git clone <repo-url>
cd econ_policy
```

*(Ask the team lead for the repo URL if you don't have it.)*

---

## Step 3: Create a Virtual Environment

```bash
python -m venv .venv
```

**Activate it:**

| Platform | Command |
|---|---|
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (CMD) | `.venv\Scripts\activate.bat` |
| macOS / Linux | `source .venv/bin/activate` |

---

## Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

If you are working from an older copy of the repo, make sure these core runtime
packages are installed:

```bash
pip install litellm python-dotenv streamlit plotly pandas
```

---

## Step 5: Set Up API Keys

Create a file named `.env` in the project root (it is gitignored — never commit it):

```
# .env
# Use one or more providers in the Streamlit sidebar.
GEMINI_API_KEY=AIza...your-key-here...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Model overrides (defaults shown)
PRISM_AGENT_MODEL=gemini/gemini-3.1-flash-lite
PRISM_SIM_MODEL=gemini/gemini-3.1-flash-lite
PRISM_EMBED_MODEL=gemini/gemini-embedding-001

# Rate-limit pacing for Gemini Flash Lite low-tier quotas.
# 15 RPM means one request starts about every 4.2 seconds.
PRISM_REQUESTS_PER_MINUTE=15
PRISM_RATE_LIMIT_RETRY_SECONDS=65

# Allow engine to read key from .env (no need to enter in UI)
PRISM_ALLOW_ENV_KEY=true
```

The sidebar supports three chat providers:

| Provider | Example chat models | Embedding support for SSR | RPM shown in UI |
|---|---|---|---|
| Gemini | `gemini/gemini-3.1-flash-lite`, `gemini/gemini-2.5-flash-lite` | `gemini/gemini-embedding-001` | Conservative/manual; check AI Studio active limits |
| OpenAI | `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini` | `text-embedding-3-small`, `text-embedding-3-large` | Official Tier 1 RPM where available |
| Claude | `anthropic/claude-opus-4-8`, `anthropic/claude-sonnet-4-6`, `anthropic/claude-haiku-4-5-20251001` | Needs OpenAI or Gemini embedding key | Official Tier 1 RPM where available |

The RPM in the UI is used for Prism's pacing estimate and request throttle. Real
limits are account/project-tier dependent, so adjust the manual RPM field if
your provider console shows a different limit. The Test buttons try to read RPM
from response headers when the provider exposes it.

**How to get a Gemini API key:**

1. Go to [Google AI Studio](https://aistudio.google.com)
2. Click **Get API key** → **Create API key**
3. Enable billing on the project (free tier is too slow for runs with N>5)
4. Set a spend cap of NT$150–200 to avoid surprises

---

## Step 6: Run the App

```bash
streamlit run prism_app.py
```

Browser opens at `http://localhost:8501`.

**Flow:**

1. **Setup** — Paste a policy/product description, or pick an example
2. **Clarify** — Answer Agent 1's scoping questions
3. **Preview** — Review and edit the generated segments + survey questions before running
4. **Run** — Watch the simulation progress bar
5. **Results** — Explore segment charts, SDB analysis, recommendations

---

## Step 7: Run a CLI Smoke Test (No Browser Needed)

To verify your API key works end-to-end:

```bash
# Piracy SDB study — N=5, ~65 API calls
python prism_smoke_piracy.py

# Fertility policy — N=5
python prism_cli_test.py
```

Output saves to `runs/` as `.jsonl` + `_report.json`. Generate the HTML report:

```bash
python prism_report.py
# Opens runs/latest_run.html
```

---

## Pipeline Architecture

```
User Input
    │
    ▼
Agent 1 — Phase A (Clarify)
    │   Reads description → generates 2–5 scoping questions
    │
    ▼
Agent 1 — Phase B (Propose)
    │   Answers + description → 3–5 segments + 12–15 survey questions
    │   Includes: Likert-5, anon/named SDB pair, multi-select, WTP, open-ended
    │
    ▼
Preview Page (UI)
    │   User reviews/edits segments and questions
    │
    ▼
Simulation Layer
    │   For each segment × question × N respondents:
    │   - Inject persona as system prompt
    │   - Inject condition framing (anonymous / named / neutral)
    │   - Async LiteLLM calls paced by PRISM_REQUESTS_PER_MINUTE
    │
    ▼
Aggregation
    │   Per segment × question: mean, SD, % yes, mean WTP, multi-select rates
    │   SDB gap = anon mean − named mean
    │
    ▼
Agent 2 — Strategist
    │   Reads aggregated stats → JSON with recommendations, risk flags, target segment
    │
    ▼
Results (UI + HTML Report)
```

---

## Key Concepts

### Social Desirability Bias (SDB) Pair

Every run includes two versions of one sensitive question:

- **Anonymous condition** — "Your response is fully anonymous..."
- **Named condition** — "Your name will be recorded and may be reviewed..."

The **SDB gap** (anon − named) measures how much respondents self-censor. A large gap signals a taboo topic where real-world surveys systematically underreport true attitudes.

### Segments

Agent 1 generates 3–5 stakeholder personas. Each has:

- **Name** — short label (e.g., "Urban Young Professional")
- **Description** — vivid 2–4 sentence persona (injected as system prompt)
- **Weight** — estimated population share (sums to 1.0)
- **Rationale** — why this group matters for the study

### N Per Cell

`n_per_cell` controls how many simulated respondents answer each question per segment. Higher N = more stable estimates, more API cost.

| N | Total calls (4 seg × 14 Q) | Cost (approx) |
|---|---|---|
| 5  | 280  | ~NT$1    |
| 20 | 1,120 | ~NT$4   |
| 50 | 2,800 | ~NT$10  |

---

## Git Workflow

```bash
git pull                     # sync before starting work
git checkout -b feature/my-feature   # new branch for your changes
# ... make changes ...
git add prism_app.py prism_engine.py
git commit -m "feat: short description of change"
git push -u origin feature/my-feature
# open a pull request on GitHub
```

**Never commit `.env`** — it contains your API key.

---

## Common Issues

| Problem | Fix |
|---|---|
| `RateLimitError` during simulation | Keep `PRISM_REQUESTS_PER_MINUTE=15` for Flash Lite low-tier quotas, or reduce N per cell |
| Gemini `503` / `high demand` during survey generation | Prism now retries transient provider errors with backoff. If it still fails after retries, wait a few minutes or temporarily switch to another Gemini model in Advanced model config |
| Clarify fails with `No JSON object found` | Agent 1 clarify now retries once with a compact JSON-only prompt and a larger response budget. If this still happens, rerun with a less congested chat model |
| Open or SSR responses look truncated | Simulation now uses question-type-specific token budgets, retries once when `finish_reason=length`, and surfaces incomplete text in the Quality tab |
| `RuntimeError: No API key provided` | Add `PRISM_ALLOW_ENV_KEY=true` to `.env`, or enter key in the UI sidebar |
| `ModuleNotFoundError: litellm` | Run `pip install litellm` inside the `.venv` |
| Streamlit shows blank page | Check that you activated the venv before running |
| `asyncio.run()` error on Windows | Upgrade Python to 3.11+, or run via Streamlit (not plain Python) |

---

## Contact

Questions → reach the team lead or open a GitHub issue.
