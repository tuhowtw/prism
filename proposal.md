---
title: "Prism: Automated Market Research Simulation via Multi-Agent LLMs"
subtitle: "One input, refracted into many stakeholder perspectives"
date: "March 2026"
---

# Prism: Automated Market Research Simulation via Multi-Agent LLMs

*One input, refracted into many stakeholder perspectives* — Economic Policy Analysis Project Proposal

---

## 1. Motivation and Research Gap

Market research is a prerequisite for sound product development and policy design. Yet traditional instruments — conjoint studies, focus groups, consumer panels — are slow, expensive, and static. A nationally representative conjoint survey can cost tens of thousands of dollars and take months to field. By the time results are available, the product landscape may have already shifted.

Recent work demonstrates that Large Language Models (LLMs) can simulate consumer preferences with surprising fidelity. Brand, Israeli and Ngwe (2023) show that querying GPT-3 hundreds of times — varying price, demographics, and product attributes — yields demand curves and willingness-to-pay estimates that match real consumer survey benchmarks. Their conjoint study with 10,800 LLM responses cost **under $3 and took 35 minutes**, versus thousands of dollars and several weeks for a comparable human survey.

However, this potential remains locked behind a manual, researcher-intensive workflow. A practitioner with a new product concept must:

1. Manually identify relevant target demographics
2. Hand-craft survey questions appropriate to the product
3. Write and execute API calls for each demographic segment
4. Aggregate results and interpret findings themselves

**The gap we address:** there is no end-to-end system that takes a product or policy description as input and automatically produces market research results with strategic recommendations. We build that system.

---

## 2. Project Overview

**Prism** is a multi-agent pipeline that automates the full market research workflow for any product or policy. Given a plain-language description of a product concept or policy proposal, the system:

1. Identifies and weights the relevant target audience
2. Designs a tailored survey instrument
3. Simulates statistically significant responses across demographic segments via parallel LLM API calls
4. Aggregates results, performs distributional analysis, and generates actionable recommendations

The system sits at the intersection of **beauty contest dynamics** (agents forming beliefs about what others will believe), **prompt engineering for policy**, and **multi-agent simulation** — the three pillars of this course's applied track.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     USER INPUT                          │
│   "A fertility subsidy of NT$200,000 for the first      │
│    child, targeted at urban households aged 25–40"      │
└──────────────────────────┬──────────────────────────────┘
                           │
               ┌───────────▼───────────┐
               │    AGENT 1            │
               │  Audience Analyst     │
               │                       │
               │  • Identifies target  │
               │    demographic groups │
               │  • Assigns sampling   │
               │    weights per group  │
               │  • Designs N survey   │
               │    questions          │
               └───────────┬───────────┘
                           │
          ┌────────────────▼────────────────┐
          │         SIMULATION LAYER        │
          │                                 │
          │  For each persona × question:   │
          │  Parallel Claude API calls      │
          │  (300+ responses per cell)      │
          │                                 │
          │  System prompt:                 │
          │  "You are a [age/gender/        │
          │   location/income/lifestyle]    │
          │   person. Answer as this        │
          │   individual would."            │
          └────────────────┬────────────────┘
                           │
               ┌───────────▼───────────┐
               │    AGENT 2            │
               │  Analysis & Strategy  │
               │                       │
               │  • Aggregates by      │
               │    segment & weight   │
               │  • Statistical tests  │
               │  • Perception gaps    │
               │  • Strategic recs     │
               └───────────┬───────────┘
                           │
               ┌───────────▼───────────┐
               │      OUTPUT           │
               │  Structured Report    │
               │  + Dashboard          │
               └───────────────────────┘
```

---

## 4. Agent Design

### 4.1 Agent 1 — Audience Analyst & Survey Designer

**Input:** Raw product/policy description (free text)

**Tasks:**

*Audience segmentation:* Agent 1 reasons about who is directly affected by or interested in the proposal. It outputs a structured list of demographic segments (e.g., urban women aged 25–35, rural households with existing children, employers of childbearing-age workers) with assigned population weights derived from general knowledge or provided data.

*Survey design:* Agent 1 generates a battery of questions appropriate to the research objective, drawing on conjoint methodology:
- **Likert-scale perception questions** ("How appealing do you find this policy?")
- **Willingness-to-pay / behavioral intent questions** ("Would this subsidy change your family planning decision?")
- **Attribute trade-off questions** (varying key policy parameters to recover preference elasticities)
- **Open-ended questions** for qualitative texture

**Prompt engineering focus:** The agent receives a structured prompt that distinguishes between the product brief, the research objective, and the audience context. Chain-of-thought prompting is used to ensure the segment weights are grounded in explicit reasoning.

### 4.2 Simulation Layer — Synthetic Respondents

**Persona injection:** Each API call includes a detailed system prompt constructing the respondent's identity:

```
You are a [gender], [age] years old, living in [city/region].
Your household income is approximately [NT$X] per year.
You [are/are not] married. You [have/do not have] children.
Your main occupation is [X]. In your free time, you enjoy [Y].
You are participating in a survey. Answer honestly as this person would,
based on your circumstances and values. Do not add explanation.
```

**Statistical design (following Brand et al. 2023):**
- Temperature set to 1.0 to maximize response heterogeneity
- Minimum 300 responses per demographic × question cell
- Questions randomized in order to counter order-bias effects
- Each response elicited independently (no batching) to avoid answer bunching

**Parallelism:** Async API calls across all cells simultaneously, with rate limiting and retry logic.

### 4.3 Agent 2 — Aggregator & Strategist

**Input:** Raw simulated responses (structured JSON)

**Tasks:**

*Aggregation:* Responses are weighted by segment population weights. Descriptive statistics (mean, median, IQR) are computed per segment and overall.

*Distributional analysis:*
- Cross-segment perception gap analysis (which groups are most/least receptive?)
- Price/attribute elasticity curves (if conjoint-style questions were used)
- Sentiment clustering for open-ended responses

*Strategic recommendations:* The agent synthesizes findings into:
- A **product/policy viability verdict** (likely uptake and key drivers)
- **Marketing targeting recommendations** (highest-receptivity segments)
- **Design modification suggestions** (which attributes to adjust and how)
- **Risk flags** (segments with strong negative reactions)

---

## 5. Prompt Engineering Strategy

Prompt engineering is the core technical contribution of this project. We develop and test prompts at three layers:

| Layer | Key Design Choices |
|---|---|
| **Persona construction** | Specificity calibration — too sparse loses segment validity; too detailed loses generalizability. We test 3 levels of detail. |
| **Question framing** | First-person vs. third-person framing; explicit vs. implicit price anchoring; order randomization |
| **Response format** | Structured JSON output with a defined schema to enable reliable parsing; numeric scales over free text where possible |
| **Aggregation prompt** | Chain-of-thought reasoning for the strategy agent; explicit instruction to ground recommendations in the data |

We follow Brand et al.'s finding that **direction of effects is robust to prompt variation but magnitude is sensitive**. Our evaluation therefore focuses on ordinal rankings across segments (which group is most receptive?) rather than precise point estimates.

---

## 6. Evaluation Metrics

We evaluate Prism on at least three dimensions:

| Metric | Description | Method |
|---|---|---|
| **Internal consistency** | Do responses follow economic logic? (higher income → lower price sensitivity; higher subsidy amount → higher acceptance) | Vary parameters systematically; test for monotonicity |
| **Cross-segment discriminability** | Does the system surface meaningful differences across demographic groups? | ANOVA across segments; effect size (Cohen's d) |
| **Benchmark calibration** (where available) | Do LLM-simulated responses match existing survey data on similar topics? | Compare to published survey data on fertility intentions, housing preferences, or consumer panels |
| **Prompt sensitivity** | How stable are conclusions across paraphrase variants of the input? | Run 5 prompt variants; measure rank-order correlation of segment scores |
| **Turnaround time vs. cost** | Wall-clock time and API cost per full research run | Log and report |

---

## 7. Application Domain

For the prototype, we apply Prism to **fertility policy in Taiwan**, specifically simulating responses to a proposed childcare subsidy for urban households. This domain is chosen because:

- It is a live policy debate in Taiwan with strong demographic stakes
- Multiple, clearly defined stakeholder groups (young couples, employers, policymakers, grandparents)
- Existing survey benchmarks exist (government fertility intention surveys) for partial validation
- It illustrates the tool's value for **policy design**, not only commercial products

The system is intentionally domain-agnostic; the same pipeline applies to product launches, pricing experiments, or communication strategy testing.

---

## 8. Alignment with Course Rubric

| Rubric Criterion | Our Coverage |
|---|---|
| **Identify inefficiency / research gap** | Traditional market research is slow and expensive; no automated pipeline exists |
| **AI system design** | Multi-agent LLM pipeline with structured prompt engineering at each stage |
| **Optional: Agent workflow** | Yes — two-agent architecture with intermediate state passing |
| **Impact on information asymmetry** | Reduces the information gap between resource-rich firms and smaller players who cannot afford professional market research |
| **Impact on transaction costs** | Cuts research costs from ~$10,000+ to ~$10–50 per run |
| **Measurable evaluation metrics** | Internal consistency, cross-segment discriminability, benchmark calibration, prompt sensitivity, cost/time |

---

## 9. Technology Stack

| Component | Tool |
|---|---|
| LLM API | Anthropic Claude (claude-sonnet-4-6) |
| Orchestration | Python with `asyncio` for parallel API calls |
| Data processing | `pandas`, `scipy` |
| Visualization | `plotly` / `seaborn` |
| Web UI | FastAPI (backend) + React (frontend) |
| Output | Markdown report + interactive dashboard |

---

## 10. References

Brand, J., Israeli, A., & Ngwe, D. (2023). *Using GPT for Market Research*. MSI Working Paper Series, Report 23-131.

Horton, J. J. (2023). *Large Language Models as Simulated Economic Agents: What Can We Learn from Homo Silicus?* NBER Working Paper 31122.

MiroFish (2024). *AI-Powered Prediction Engine*. GitHub: https://github.com/666ghj/MiroFish

Argyle, L., Busby, E., Fulda, N., Gubler, J., Rytting, C., & Wingate, D. (2022). *Out of One, Many: Using Language Models to Simulate Human Samples*. Political Analysis.
