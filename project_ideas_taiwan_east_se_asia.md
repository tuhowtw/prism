# Economic Policy AI Project Ideas

## Taiwan and East/SE Asia Focus

This document proposes team project ideas aligned with the course requirements:
- Identify an inefficiency or research gap
- Use AI system design (LLM, optional RAG, optional agent workflow)
- Show impact on information asymmetry, transaction costs, market failure, or empirical gaps

## 1) Taiwan Central Bank Watcher 2.0
**Core problem**: Policy communication is complex and hard to digest quickly.

**What to build**:
- A RAG dashboard that ingests Taiwan central bank statements, speeches, hearing transcripts, and major financial news
- Multi-agent pipeline for document retrieval, sentiment/stance classification (hawkish vs dovish), and summary generation
- Scenario simulator for inflation/interest-rate paths

**Why it fits the rubric**:
- Reduces information asymmetry for firms, households, and investors
- Strong empirical validation via event-study style comparison with FX, bond yields, and inflation expectations

## 2) Typhoon-to-Price Early Warning (Taiwan)
**Core problem**: Weather shocks create sudden food price volatility and supply disruptions.

**What to build**:
- Data pipeline combining weather alerts, logistics/port data, and market price data
- AI model for 2-4 week risk forecasts by product and region
- LLM interface that explains likely channels (transport bottleneck, crop damage, inventory shortage)

**Why it fits the rubric**:
- Addresses disaster-related market failure
- Lowers transaction costs for retailers and local governments

## 3) ASEAN-Taiwan SME Tariff and Rules Copilot
**Core problem**: SMEs underuse tariff preferences because trade rules are too complex.

**What to build**:
- RAG assistant for HS code support, rules of origin checks, and required documentation
- Agent workflow for route-specific compliance checklists
- Explanation mode in plain language for non-experts

**Why it fits the rubric**:
- Reduces transaction costs and compliance errors
- Clear metrics: time saved, filing error reduction, effective tariff reduction

## 4) Migrant Care Labor Matching (Taiwan-Indonesia-Philippines-Vietnam)
**Core problem**: Long-term care labor markets face severe matching frictions.

**What to build**:
- Matching prototype using constrained optimization + LLM-based profile interpretation
- Contract transparency module (wage terms, skill requirements, language fit)
- Policy simulation for shortage reduction under different subsidy or training designs

**Why it fits the rubric**:
- Reduces search and mismatch costs
- High relevance to aging, welfare, and labor policy

## 5) East Asia Fertility Policy Simulator (Taiwan, Japan, Korea)
**Core problem**: Very low fertility with uncertain effects of policy packages.

**What to build**:
- Comparative policy RAG over fertility policy documents and outcomes
- Simulation dashboard testing childcare subsidies, tax credits, and housing support bundles
- Output: labor-force, fiscal burden, and inequality projections

**Why it fits the rubric**:
- Addresses an empirical gap in cross-country policy synthesis
- Strong tie-in to welfare and dynamic optimization topics

## 6) Taiwan Housing Speculation and Vacancy Intelligence
**Core problem**: Information opacity in property markets can amplify speculative behavior.

**What to build**:
- AI pipeline combining transactions, rental listings, zoning updates, and policy announcements
- Neighborhood-level risk scoring for vacancy and speculative pressure
- Explainable reports for policy targeting

**Why it fits the rubric**:
- Reduces information asymmetry
- Can reveal patterns that traditional approaches miss

## 7) Semiconductor Supply Chain Shock Radar (Taiwan + East Asia)
**Core problem**: Firms struggle to track early warning signals for geopolitical and logistics disruptions.

**What to build**:
- NLP monitor of official announcements, shipping disruptions, sanctions updates, and earnings calls
- Agent-generated risk map and contingency recommendations
- User interface for procurement and policy teams

**Why it fits the rubric**:
- Reduces transaction and coordination costs
- Practical business and policy value

## 8) Coastal Fishery Externality Monitor (Taiwan + SE Asia)
**Core problem**: Overfishing and illegal activity create resource externalities.

**What to build**:
- AI fusion of vessel movement data, weather/ocean conditions, and enforcement records
- LLM-generated enforcement and sustainability recommendations
- Pilot dashboard for local regulators

**Why it fits the rubric**:
- Direct market-failure case (externalities and common-resource governance)
- Clear welfare and sustainability angle

---

## Recommended Top 3 (Best balance of score potential and feasibility)
1. Taiwan Central Bank Watcher 2.0
2. ASEAN-Taiwan SME Tariff and Rules Copilot
3. Typhoon-to-Price Early Warning

## Suggested Midterm Deliverables
- Problem definition and stakeholder map
- Data inventory and quality audit
- Baseline prototype (single workflow)
- Prompt appendix version 1 (hallucination controls and validation checks)
- Evaluation plan with at least 3 measurable metrics

---

## Data Sources Deep Dive

### A) Taiwan Central Bank Watcher 2.0: Recommended Data Stack

#### 1) Primary policy and market sources (official)
| Source | What you can extract | Frequency | Access mode |
| --- | --- | --- | --- |
| Central Bank of the Republic of China (Taiwan) Data Open portal: https://www.cbc.gov.tw/tw/lp-1032-1.html | Open dataset list and links to machine-readable files | Mixed | HTML index to files/API |
| CBC Financial Statistics page: https://www.cbc.gov.tw/tw/np-521-1.html | Financial indicators, monthly bulletin links, banking and rate tables | Daily/Monthly/Quarterly | HTML, linked files |
| CBC Statistical Database: https://cpx.cbc.gov.tw/Tree/TreeSelect | Structured time series; page explicitly references API docs | Mixed | Database UI + API docs |
| CBC rates page: https://www.cbc.gov.tw/tw/np-369-1.html | Policy rates, bank posted rates, and text endpoint (e.g., bkrldc.txt) | Daily | HTML + TXT |
| CBC NTD/USD interbank close: https://www.cbc.gov.tw/tw/lp-645-1.html | Daily close exchange rate history | Daily | HTML table |
| CBC open market operations: https://www.cbc.gov.tw/tw/np-1172-1.html | Daily OMOs and related statistics | Daily | HTML + linked tables |
| DGBAS National Statistics: https://eng.stat.gov.tw/ | CPI, GDP, labor, release calendar, and statistical database | Monthly/Quarterly | HTML + statistical tables |

#### 2) Suggested minimum feature set
- Text features: policy statements, post-meeting briefing text, open market operation notes.
- Numeric features: policy rate changes, interbank overnight rate, NTD/USD close, CPI yoy, industrial production, unemployment.
- Event features: scheduled release calendar events and surprise indicators.

#### 3) Practical ingestion notes
- Build two pipelines: 
	1) document pipeline for RAG (policy text, press releases), 
	2) time-series pipeline for forecasting and event study.
- Prioritize official machine-readable endpoints first (TXT/XLS/API) before scraping page tables.
- Keep release timestamps and publication lag metadata for proper event-window backtesting.

### B) East Asia Fertility Policy Simulator: Recommended Data Stack

#### 1) Core demographic outcomes
| Source | Coverage | What you can extract | Access mode |
| --- | --- | --- | --- |
| Taiwan Household Registration Statistics (MOI): https://www.ris.gov.tw/app/en/346 and End-of-Year tables https://www.ris.gov.tw/app/en/3910 | Taiwan | Live births, age-specific fertility, total fertility rate, by county and education (tables 8-13 visible on site) | XLS/ODF downloads |
| DGBAS survey pages (incl. women's marriage/fertility/employment survey links): https://eng.stat.gov.tw/ | Taiwan | Household, labor, and demographic context variables | Statistical tables |
| Japan e-Stat Developers: https://www.e-stat.go.jp/en/developer and API entry https://www.e-stat.go.jp/api/en | Japan | Official statistics via API (JSON/CSV/XML), plus downloadable tables | API + file download |
| Japan Population Estimates: https://www.stat.go.jp/english/data/jinsui/index.html | Japan | Population baseline and demographic controls | Official tables |
| Korea KOSIS Statistical Database: https://kosis.kr/eng/statisticsList/statisticsListIndex.do?vwcd=MT_ETITLE&menuId=M_01_01 | Korea | Population and social statistics with table downloads | Table download (OpenAPI also available on KOSIS portal) |
| World Bank API fertility indicator (JPN, KOR): https://api.worldbank.org/v2/country/JPN;KOR/indicator/SP.DYN.TFRT.IN?format=json | Japan, Korea | Harmonized long-run TFR series | JSON API |

#### 2) Important coverage caveat
- World Bank API query for Taiwan fertility (TWN) currently returns empty results: https://api.worldbank.org/v2/country/TWN/indicator/SP.DYN.TFRT.IN?format=json
- For Taiwan, use MOI household registration and DGBAS sources as primary truth.

#### 3) Policy-variable layer (for simulator interventions)
- OECD Data Explorer: https://data-explorer.oecd.org/ for cross-country family, labor, and social context indicators.
- National policy text corpus (for RAG):
	- Taiwan MOI and relevant ministry policy pages,
	- Japan ministry/agency policy documents,
	- Korea ministry policy documents.

#### 4) Suggested modeling dataset schema
- Unit: country-year (baseline) + optional subnational panel for Taiwan counties.
- Outcomes: TFR, age-specific fertility, births by mother age.
- Controls: wages, unemployment, housing burden proxy, childcare capacity proxy, marriage/divorce rates.
- Policy treatments: childcare subsidy, parental leave generosity, tax credit scope, housing support.

### Fast Start (1-week data sprint)
1. Pull Taiwan fertility base tables from RIS (tables 8-13) and clean to long format.
2. Pull Japan/Korea baseline TFR via World Bank API and cross-check with national sources.
3. Build a single harmonized data dictionary (variable name, definition, unit, source URL, update frequency).
4. Create a simple data quality report (missingness, lag, breaks, and revision behavior).
