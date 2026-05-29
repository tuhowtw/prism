# Prism — Session Log

Each session: date, what changed, files touched, decisions made.

---

## 2026-05-29 — Token Budget and Truncation Reliability Follow-up

**Objective:** Fix the two open truncation issues without splitting large files:
Agent 1 clarify JSON truncation and simulation open-response truncation.

### User constraints and decisions

| Decision | Result |
|---|---|
| Do not split large files | Kept the fix inside the existing Prism files. No large-file decomposition was done. |
| Record changes in markdown | This entry records the implementation and verification results in English. |
| User will run one final app test | Local compile/unit tests were completed first; the app is ready for the user's final run check. |

### Files changed

| File | What changed |
|---|---|
| `prism_engine.py` | Added `ChatResult` so LiteLLM `finish_reason` is captured. `run_agent1_clarify` now starts with a smaller 2048-token budget and retries once with a compact JSON-only prompt at 4096 tokens if parsing fails. Simulation now uses question-type-specific `max_tokens`: tiny budgets for structured answers, 1024 tokens for `open` and SSR free-text, and one retry with a larger budget when `finish_reason == "length"`. Open and SSR prompts now require one complete sentence with terminal punctuation. Quality analysis now flags responses that hit max tokens, incomplete open responses, and SSR free-text that is too short for reliable embedding. |
| `prism_app.py` | The `Quality` tab now displays the new truncation/completeness detail rows: `max_tokens`, `incomplete_open`, and `short_ssr`. |
| `prism_session.py` | Saved and reloaded `finish_reason` for each simulated response so truncation evidence survives run export/import. |
| `tests/test_prism_core.py` | Added tests for type-specific token budgets, free-text completion heuristics, and `finish_reason` response serialization. |
| `GUIDEBOOK.md` | Added troubleshooting notes for clarify JSON truncation and open/SSR response truncation. |
| `SESSION_LOG.md` | Added this implementation record. |

### Issue coverage

| Issue | Fix |
|---|---|
| Agent 1 clarify response can be cut off before valid JSON is complete | Retry only the clarify call with a compact JSON-only prompt and larger response budget. This avoids raising the ceiling for every Agent 1 call. |
| Simulation `open` and SSR free-text responses can be truncated by a shared 256-token limit | Replaced the shared limit with question-type-specific budgets and a `finish_reason == "length"` retry guard. |
| Truncation was invisible at runtime | Persisted `finish_reason` and added Quality-tab warnings/detail rows so bad text is visible before reporting. |

### Verification run

```bash
.venv/bin/python -m py_compile prism_engine.py prism_app.py prism_session.py macro_simulation_demo.py
.venv/bin/python -m unittest discover -s tests -v
```

Result:

- Python compile check passed.
- Unit tests passed: `13` tests OK.
- Streamlit restarted on `http://localhost:8501`.
- Localhost health check passed with `HTTP/1.1 200 OK`.
- The LiteLLM model-cost-map network warning appeared during tests, but tests used the local fallback and completed successfully.

### Runtime checks

User-run confirmation was checked from `/Users/mz/Downloads/20260529_133827_n3`.

| Check | Result |
|---|---|
| Response persistence | `responses.json` was exported with the run. |
| Response count | `108/108` expected responses were present. |
| Finish reasons | All `108` responses had `finish_reason = "stop"`; none ended with `length`. |
| Truncation quality checks | `length_finished_cells`, `incomplete_open_cells`, and `short_ssr_cells` were all empty. |
| SSR coverage | All 9 SSR questions had PMFs for all 9 responses each. |
| Remaining warning | Only `n_per_cell is below 5`, which means the run is a smoke test rather than final evidence. |

Conclusion: the clarify/open-response token truncation fixes passed the user-run
runtime check.

Second user-run confirmation was checked from `/Users/mz/Downloads/20260529_141837_n10`
and `/Users/mz/Downloads/20260529_141837_n10_report.md`.

| Check | Result |
|---|---|
| Response persistence | `responses.json` and `manifest.json` were exported with the run. |
| Response count | `360/360` expected responses were present. |
| Finish reasons | All `360` responses had `finish_reason = "stop"`; none ended with `length`. |
| Truncation quality checks | `length_finished_cells`, `incomplete_open_cells`, and `short_ssr_cells` were all empty. |
| Quality warnings | No warnings were reported for the `n=10` run. |
| Duplicate cells | Duplicate cell rate was `11.1%`; this came from two direct Likert SDB cells, one WTP cell with all-zero responses, and one multi-select cell. It is not a truncation failure. |
| SSR coverage | All `210` SSR responses were free-text responses with PMFs; no short numeric SSR responses were found. |
| Report review | The report was internally consistent, but the generic `wtp` label read as `mean WTP` even when the question asked for a minimum required subsidy amount. |

Follow-up fix: changed the report builder and Agent 2 summary prompt from
`mean WTP` to `mean numeric response` for `wtp` fields so future reports do not
mislabel policy subsidy-amount questions as willingness-to-pay.

Verification after this label fix:

```bash
.venv/bin/python -m py_compile prism_engine.py prism_app.py prism_session.py macro_simulation_demo.py
.venv/bin/python -m unittest discover -s tests -v
```

Result:

- Python compile check passed.
- Unit tests passed: `13` tests OK.

### Suggested high-acceptance policy prompt

For a next Prism run that is intentionally designed to test a policy likely to
receive broad support, use this policy input:

```text
A Taiwan family-support policy called "0-6 Care Credit." Every child from birth to age 6 receives NT$8,000 per month in a universal care credit, paid automatically after household registration with no separate application and no income means-testing. The credit can be used for licensed childcare, preschool fees, after-school care, diapers, formula, pediatric visits, and parent-approved caregiving expenses. Low-income, single-parent, and disability households receive an extra NT$4,000 monthly top-up. Parents can choose either monthly payments or a direct discount through registered childcare providers. The program includes a privacy guarantee: subsidy data cannot be used for tax audits or unrelated welfare investigations. Funding comes from a dedicated luxury property surcharge and unused birth-incentive budgets. The policy is guaranteed for 6 years per child so families can plan long term.
```

Rationale:

- Universal eligibility avoids hard cutoff resentment.
- Automatic payment reduces administrative friction.
- Monthly support better matches recurring childcare costs than a one-time bonus.
- Flexible eligible expenses make the benefit relevant across family types.
- Privacy guarantees address the tax-audit and data-surveillance backlash seen in the `n=10` run.
- Targeted top-ups preserve progressivity without excluding middle-income families.
- A 6-year guarantee improves long-term planning confidence.

Suggested clarify answers:

- Primary goal: `Test public support and adoption barriers`.
- Target segments: `Young parents, middle-income households, low-income families, childless taxpayers`.
- Success metric: `High perceived fairness and high intent to use`.

### Current handoff state

- Local app is running at `http://localhost:8501`.
- Latest code validation: Python compile passed and `13` unit tests passed.
- `SESSION_LOG.md` and `GUIDEBOOK.md` contain the completed English records for the current work.
- No API keys were written to markdown.

---

## 2026-05-28 — Prism Reliability, Rate Limit, Quality, and Validation Pass

**Objective:** Improve Prism without splitting large files, make Gemini Flash Lite
usable under a 15 RPM limit, preserve full run data, add quality/reporting
features, and record validation/stability work in markdown.

### User constraints and decisions

| Decision | Result |
|---|---|
| Do not split large files | Kept changes inside the existing files; no large-file decomposition was done. |
| Gemini 3.1 Flash Lite RPM is 15 | Added request pacing based on `PRISM_REQUESTS_PER_MINUTE=15`, about 4.2 seconds between request starts. |
| Make the project more defensible | Added validation/stability notes, quality checks, report mode, and clearer limitations language. |
| Preserve generated run data | Added `responses.json` persistence and reload support. |
| Keep API keys out of git | `.env` remains gitignored; no key was written to markdown. |

### Files changed

| File | What changed |
|---|---|
| `.gitignore` | Added `.cache/` so local Matplotlib cache files are not committed. |
| `requirements.txt` | Added/normalized runtime dependencies: `litellm`, `python-dotenv`, `streamlit`, `plotly`, `pandas`, `matplotlib`, `seaborn`, `numpy`, `anthropic`, `beautifulsoup4`, `lxml`, `requests`. |
| `GUIDEBOOK.md` | Updated install instructions to use `pip install -r requirements.txt`; documented Gemini/OpenAI/Claude provider setup, embedding model choices, 15 RPM pacing, model-tier RPM guidance, and rate-limit troubleshooting. |
| `macro_simulation_demo.py` | Set `MPLCONFIGDIR` to `.cache/matplotlib` before importing Matplotlib so the demo does not write cache files outside the project. |
| `prism_engine.py` | Added runtime model configuration for agent, simulation, embedding, response language, and requests-per-minute pacing. Changed default embedding model to `gemini/gemini-embedding-001`. Added split chat/embedding API-key support for simulation so Claude chat can use OpenAI or Gemini embeddings. Added longer rate-limit retry waits and transient Gemini/provider retry handling for `503`, high-demand, timeout, and connection errors. Added request/runtime estimator. Added respondent micro-profiles per replicate to reduce repeated answers. Made SDB pairs optional instead of forced. Added auto-SSR defaults for key neutral Likert questions. Added response-language instruction. Added quality analysis for missing, duplicate, flat Likert, invalid parse, SSR, and SDB checks. |
| `prism_app.py` | Added provider selection for Gemini, OpenAI, and Claude. Added chat and embedding API-key controls, separate chat/embedding key tests, model preset dropdowns with RPM labels, manual RPM pacing, and best-effort RPM header detection. Added embedding model and response-language controls. Applied model config before clarify/propose/simulation/analysis. Added preview runtime estimate, SSR count, and low-`n` warnings. Preserved SSR toggles and anchors in the preview editor. Persisted raw responses and quality reports. Added results `Quality` tab and `Report` tab with downloadable markdown. Fixed results layout for runs with no SDB pair. Replaced deprecated Streamlit `use_container_width` calls with `width="stretch"`. Cleared stale responses/results when regenerating a survey. |
| `prism_session.py` | Added `responses.json` save/load helpers. Preserved SSR fields (`use_ssr`, `anchors`) in question serialization. Added zip-import path traversal protection. |
| `tests/test_prism_core.py` | Added unit tests for parsing, aggregation/SDB, SSR serialization, response serialization, response persistence, unsafe zip rejection, runtime model config, respondent variation, transient Gemini `503` detection, request estimation, and quality analysis. |
| `PRISM_IMPROVEMENT_PLAN.md` | Recorded the fertility validation/stability plan and filled the completed micro stability table. |
| `VALIDATION_FERTILITY.md` | Added benchmark validation for the Taiwan fertility subsidy demo. |
| `VALIDATION_SCOOTER.md` | Added benchmark validation for the electric-scooter rebate demo using Taiwan subsidy, environment, Gogoro, and research sources. |
| `SESSION_LOG.md` | This entry records the full pass. |

### Completed run analysis

| Run | What was checked | Result |
|---|---|---|
| `runs/20260528_213554_n3/` | Old scooter run duplicate check | 30 of 36 segment-question cells were exact duplicates, showing the old simulation was too repetitive. |
| `runs/20260528_220202_n3/` | New scooter run after respondent micro-profiles | 108 responses, 36 cells, all cells had 3 distinct micro-profiles. Duplicate cells dropped to 19 of 36, but `n_per_cell=3` remains a smoke test. |
| `runs/stability_fertility_micro_index.json` | Fertility prompt-framing stability index | Recorded neutral/optimistic/skeptical micro stability comparison. |
| `runs/20260528_193300_micro_optimistic_micro/` | Fertility optimistic micro run | Used in the stability table. |
| `runs/20260528_193318_micro_skeptical_micro/` | Fertility skeptical micro run | Used in the stability table. |

### Validation notes added

| Markdown | Purpose |
|---|---|
| `VALIDATION_FERTILITY.md` | Shows that Prism's fertility findings match external evidence on housing cost, childcare/work-family support, and the limited effect of cash-only fertility subsidies. |
| `PRISM_IMPROVEMENT_PLAN.md` | Records the fertility stability test and labels each finding as strong, medium, framing-sensitive, or unvalidated. |
| `VALIDATION_SCOOTER.md` | Shows that Prism's scooter findings are directionally supported on total cost, battery subscription dependence, station convenience, and environmental rationale; marks the 6-month deadline and repairability backlash as hypotheses. |

### Verification run

```bash
.venv/bin/python -m py_compile prism_engine.py prism_app.py prism_session.py macro_simulation_demo.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python test_simulation.py
```

Result:

- Python compile check passed.
- Unit tests passed: `11` tests OK.
- Macro simulation smoke test passed.
- SSR embedding smoke test passed against Gemini embeddings:
  - negative response EV `2.22`
  - neutral response EV `3.05`
  - positive response EV `3.71`
- Generated `__pycache__` directories were removed after testing.

### Known limits after this pass

- Full high-`n` Prism stability reruns were not run because Gemini quota/time can
  still be expensive under 15 RPM.
- `n_per_cell=3` is now clearly labeled as a smoke test. Use `n_per_cell=5` for
  a class demo and `10+` for stronger evidence.
- Duplicate Likert values can still happen because 1-5 scales are coarse. SSR
  and larger `n_per_cell` reduce this, but do not turn synthetic respondents
  into real survey data.
- The 6-month scooter deadline and DIY repairability findings are useful
  hypotheses, not externally validated conclusions yet.

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
