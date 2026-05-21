# Prism — Session Log

Each session: date, what changed, files touched, decisions made.

---

## 2026-05-21 — SSR (Semantic Similarity Rating) Implementation

**Objective:** Replace direct Likert integer elicitation (DLR) with free-text + cosine-similarity mapping (SSR), following Maier et al. (2025) *"LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"*.

**Motivation:** DLR produces narrow, regression-to-mean distributions (KS sim ~0.26). SSR lifts this to ~0.88 by asking LLMs for free-text, embedding responses, and projecting onto a Likert scale via cosine similarity to anchor statements.

### Design decisions

| Decision | Choice | Reason |
|---|---|---|
| Embedding model | `text-embedding-3-small` (OpenAI) | Paper default; ~$0.02/1M tokens |
| Scope | `likert5` only, opt-in via `use_ssr` flag | A/B comparison possible in same run |
| Anchors | Agent 1 generates; fallback to generic templates | Domain-specific > generic |
| pmf params | ε=0, T=1 | Paper defaults; good starting point |

### Files changed

| File | Change |
|---|---|
| `prism_engine.py` | `SurveyQuestion`: +`use_ssr`, +`anchors`. `SimulatedResponse`: +`pmf`. New SSR helpers: `_aembed`, `_ssr_score`, `_cosine`, `_resolve_anchors`, `_prewarm_anchor_cache`. `_build_question_instruction`: free-text branch for SSR. `_parse_response`: pass-through raw text for SSR. `_simulate_one`: call `_ssr_score` post-LLM-call. `run_simulation_async`: pre-warm anchor cache. `_aggregate_responses`: +`sd`, +`pmf_mean`. Agent 1 system prompt: +SSR schema + instructions. Parser: +`use_ssr`, +`anchors`. |
| `prism_report.py` | SQLite `responses` table: +`pmf TEXT` column. `stdev` helper added. Likert card: shows SD per segment + SSR distribution bars (stacked SVG). |
| `prism_smoke_piracy.py` | JSONL writer: +`pmf` field. |
| `requirements.txt` | +`numpy` |
| `.env` | Added placeholder + comment for `OPENAI_API_KEY` (SSR requires this). |
| `prism_ssr_test.py` | **New.** Unit smoke test: 3 response polarity cases → verify pmf peaks at expected Likert position. |

### How to verify

```bash
# 1. Add OPENAI_API_KEY to .env
# 2. Unit test
python prism_ssr_test.py

# 3. Full pipeline smoke — piracy study with SSR on
python prism_smoke_piracy.py

# 4. Inspect distribution width vs old runs/ baseline
python prism_report.py
```

### Open items / next session

- [ ] Run `prism_ssr_test.py` with real OpenAI key to confirm pmf direction
- [ ] Update `prism_app.py` Streamlit UI — expose `use_ssr` toggle per question in Preview page
- [ ] Compare SSR vs DLR distributions side-by-side on piracy SDB study
- [ ] Consider averaging across multiple anchor sets (paper uses m=6; we use 1)

---
