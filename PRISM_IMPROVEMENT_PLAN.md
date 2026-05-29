# Prism Improvement Plan

## Project Positioning

Prism should be presented as a policy and product perception simulator, not as a
replacement for real surveys.

Recommended statement:

> Prism is a multi-agent LLM simulation tool for early-stage policy perception
> analysis. It helps identify likely stakeholder reactions, perception gaps, and
> hypotheses before expensive real-world field surveys.

This framing is important because Prism's current outputs are synthetic. They
are useful for generating hypotheses and comparing stakeholder perspectives, but
they should not be claimed as exact forecasts of citizen behavior.

## Main Weakness To Fix

The main weakness is credibility.

The project already has a working pipeline:

1. User enters a policy or product proposal.
2. Agent 1 asks clarifying questions.
3. Agent 1 creates stakeholder segments and survey questions.
4. The simulation layer generates persona-conditioned responses.
5. Aggregation computes segment-level results and social-desirability gaps.
6. Agent 2 generates recommendations.

The next task is not adding more features first. The next task is making the
methodology easier to defend.

## What Has Already Been Added

A first validation note has been created:

- `VALIDATION_FERTILITY.md`

That note compares the existing Taiwan fertility subsidy demo against external
benchmarks from Taiwan policy sources, OECD evidence, and IMF fertility-policy
analysis.

Current validation result:

| Prism finding | Real-world support | Status |
|---|---|---|
| NT$200,000 cash alone is too weak. | OECD and IMF evidence suggest cash transfers usually have limited or modest fertility effects. | Directionally supported |
| Housing cost is a major fertility barrier. | Taiwan Legislative Yuan and OECD sources identify housing cost as fertility-relevant. | Directionally supported |
| Childcare and work-family support matter. | Taiwan NDC policy and OECD evidence emphasize childcare and work-family balance. | Directionally supported |
| Income cap and installment design may create backlash. | Some support for broader eligibility, but limited direct evidence on this exact design. | Treat as hypothesis |

## Next Step: Stability Testing

The next improvement should be a stability test.

Purpose:

> Check whether Prism gives the same broad conclusions when the same policy is
> phrased slightly differently or run multiple times.

This answers the criticism:

> Is the result just one random LLM output?

## Stability Test Design

Use the Taiwan fertility subsidy case.

Base policy:

> A government policy offering NT$200,000 cash subsidy per child for the first
> two children, targeted at married couples aged 25-40 living in major urban
> centers such as Taipei, Taichung, and Kaohsiung. The subsidy is paid in
> installments over 3 years and is means-tested below NT$1.5M household income.

Run three versions:

1. Original wording.
2. More optimistic wording.
3. More skeptical wording.

Example variants:

### Variant 1: Neutral

> A government policy offering NT$200,000 cash subsidy per child for the first
> two children, targeted at married couples aged 25-40 living in major urban
> centers such as Taipei, Taichung, and Kaohsiung. The subsidy is paid in
> installments over 3 years and is means-tested below NT$1.5M household income.

### Variant 2: Optimistic

> Taiwan is considering a family-support policy that gives eligible married
> couples aged 25-40 a NT$200,000 subsidy for each of their first two children.
> The goal is to reduce early childrearing pressure and encourage young urban
> households to feel more secure about having children.

### Variant 3: Skeptical

> Taiwan is considering a NT$200,000 child subsidy for married urban couples
> aged 25-40, but the payment would be spread over 3 years and limited to
> households below NT$1.5M annual income. The study should assess whether this
> amount is enough to change fertility decisions despite housing, childcare,
> and career pressures.

Recommended run size:

- Minimum: `n_per_cell = 5`
- Better: `n_per_cell = 10`
- Stronger: `n_per_cell = 20`

For a class presentation, `n_per_cell = 5` or `10` is acceptable if API cost or
time is limited.

## Stability Table

The repository contains two completed neutral fertility runs:

- `runs/20260526_154258_n3/manifest.json`
- `runs/20260526_161832_n3/manifest.json`

Because the Gemini API hit quota/latency limits during a full rerun, the two
missing prompt variants were completed as a micro stability test:

- one fixed stakeholder segment: urban married couple, age 25-40
- one model assessment per prompt variant
- model: `gemini/gemini-2.5-flash-lite`
- index file: `runs/stability_fertility_micro_index.json`
- optimistic run: `runs/20260528_193300_micro_optimistic_micro/`
- skeptical run: `runs/20260528_193318_micro_skeptical_micro/`

This is not as strong as a full Prism rerun with new Agent 1 segments and
survey simulation, but it is enough for a first prompt-framing stability check.

| Finding | Run 1 Neutral | Run 2 Optimistic | Run 3 Skeptical | Stability |
|---|---|---|---|---|
| NT$200,000 cash alone is too weak. | Yes. Both completed neutral runs say the subsidy is insufficient or a "drop in the bucket." | Maybe. The optimistic micro run says NT$200,000 may help but may not offset long-term childrearing costs. | Yes. The skeptical micro run says NT$200,000 spread over 3 years is unlikely to be decisive. | Medium-strong. Stable direction, but optimistic framing softens the wording. |
| Housing cost is a major barrier. | Yes. Both completed neutral runs identify high urban living or housing affordability as a core barrier. | Yes. The optimistic micro run says the policy does not directly address substantial urban housing costs. | Yes. The skeptical micro run says housing costs would overshadow the subsidy. | Strong. Appears under all tested framings. |
| Childcare/work-family support is important. | Yes. Completed neutral runs mention childcare infrastructure, career-family balance, or lost career progression. | Yes. The optimistic micro run says childcare availability and work-life balance remain key concerns. | Yes. The skeptical micro run says childcare concerns require more comprehensive support than cash. | Strong. Appears under all tested framings. |
| Means-testing may create resentment. | Yes. Both completed neutral runs recommend eliminating, raising, or re-evaluating the NT$1.5M income cap. | No / not applicable. The optimistic variant did not mention means-testing. | Maybe. The skeptical micro run says the income cap may be viewed as unfair by households just above it. | Framing-sensitive. This finding appears when the income cap is included in the prompt. |
| Installment structure reduces perceived usefulness. | Yes. Both completed neutral runs criticize the 3-year installment or short-term structure. | No / not applicable. The optimistic variant did not mention installments. | Yes. The skeptical micro run says spreading payment over 3 years reduces immediate usefulness. | Medium. Stable when installment design is included, but absent when omitted from framing. |

Suggested labels:

- Strong: appears in all 3 runs.
- Medium: appears in 2 of 3 runs.
- Weak: appears in 1 of 3 runs.
- Unstable: conclusion changes direction across runs.

## Limitations Section

Use this language in the report or slides:

> Prism uses synthetic LLM respondents, so its results should be interpreted as
> directional perception signals rather than measured public opinion. The system
> can help identify likely concerns, stakeholder differences, and hypotheses for
> follow-up surveys, but it does not estimate true fertility behavior or exact
> approval rates. Results may vary with model choice, prompt wording, persona
> design, and simulation sample size. Real-world survey data is still required
> for final policy evaluation.

Shorter slide version:

> Prism is useful for hypothesis generation, not final causal measurement.

## Recommended Report Section

Add a section called:

> Validation and Credibility

Include three pieces:

1. Benchmark comparison from `VALIDATION_FERTILITY.md`.
2. Stability table from three Prism runs.
3. Limitations statement.

This makes the project much easier to defend because it directly answers:

- Why should we trust the output?
- Is the result stable?
- What does the tool not claim to do?

## Later Product Improvements

After the validation and stability layer is finished, improve the app itself.

Possible product improvements:

1. Add a "Run Stability Test" button.
2. Let users compare 2-3 prompt variants side by side.
3. Show repeated findings as stable/medium/weak.
4. Add uncertainty or variation indicators.
5. Add benchmark notes into generated reports.
6. Separate "simulated finding" from "strategic recommendation."
7. Make the report clearly label outputs as synthetic simulation results.

## Later Engineering Improvements

Only after the project is more defensible, clean up the code structure.

Possible engineering improvements:

1. Split the long Streamlit app into smaller files.
2. Separate UI, state management, storage, agents, and visualization.
3. Add tests for response parsing and aggregation.
4. Add stronger validation for run manifests.
5. Update `requirements.txt` to include all current dependencies.

These are useful, but they are lower priority than credibility for the current
presentation.

## Priority Order

1. Finish positioning statement.
2. Keep and use `VALIDATION_FERTILITY.md`.
3. Run the three-run stability test.
4. Fill the stability table.
5. Add limitations to report/slides.
6. Only then improve app features or refactor code.

## Final Recommendation

The project is already demoable. The highest-value improvement is to make it
more defensible:

> validation + stability + clear limits.

That should come before adding more features.
