# Prism Fertility Demo: Benchmark Validation Note

## Purpose

This note adds a first validation layer for Prism's Taiwan fertility subsidy demo.
It does not prove that simulated LLM respondents predict real citizens. Instead,
it tests whether Prism's qualitative conclusions align with external evidence
from Taiwan policy sources and international fertility-policy research.

Recommended framing:

> Prism is a fast hypothesis-generation and perception-simulation tool. Its
> outputs should be used to identify likely friction points and segment-level
> hypotheses before running field surveys, not as a replacement for real survey
> measurement.

## Prism Run Used

- Run: `runs/20260526_161832_n3/manifest.json`
- Policy tested: NT$200,000 cash subsidy per child for the first two children,
  targeted at married couples aged 25-40 in Taipei, Taichung, and Kaohsiung,
  paid over 3 years and means-tested below NT$1.5M household income.
- Segments:
  - Striving Young Professionals
  - Established Dual-Income Parents
  - Cautious Career-Seekers
- Sample size: `n_per_cell = 3`, so this is only a low-cost demo run.
- Prism headline result: weighted reception score `1.76 / 5`.
- Prism key insight: the subsidy was perceived as too small relative to
  structural barriers such as housing cost and career stability.

Because this run used only 3 responses per cell, the validation below should be
treated as a face-validity and directional benchmark check, not a statistical
calibration exercise.

## Benchmark Comparison

| Validation claim | Prism output | External benchmark | Assessment |
|---|---|---|---|
| Housing cost is a major fertility barrier for young urban households. | Agent 2 recommended pivoting from a one-off subsidy toward housing affordability support. It also flagged urban professionals as highly cost-burdened. | Taiwan Legislative Yuan analysis states that high housing prices are an important driver of low fertility because young people face mortgage burdens disproportionate to wages and may avoid childbearing even after marriage. OECD evidence also finds that increased household housing expenditure has a significant negative effect on total fertility rates. | Strong directional match. |
| Childcare and work-family balance matter more than a narrow birth cash payment. | Agent 2 recommended long-term structural support, including childcare infrastructure, rather than relying on NT$200,000 cash alone. | Taiwan's low-birth-rate countermeasure plan explicitly targets lower childrearing burdens, work-family balance, expanded public/quasi-public childcare, childcare subsidies, and family-friendly workplaces. OECD evidence finds public spending on early childhood education and care has a significant positive association with fertility rates. | Strong directional match. |
| One-time or narrow cash benefits alone are unlikely to strongly raise fertility. | Prism's main conclusion was that NT$200,000 is a "drop in the bucket" and unlikely to change family-planning decisions. | OECD concludes that monetary transfers generally have no or only modestly positive effects on fertility, with effects often transitory. IMF research on Japan similarly finds limited evidence that cash transfers strongly support fertility and notes childcare facilities may have much larger effects. | Strong directional match. |
| Means-testing can create perceived exclusion or friction. | Agent 2 recommended re-evaluating the NT$1.5M income cap because it may alienate urban professionals facing high living costs. | Taiwan policy adjustments have moved toward broader support in some areas, including cancellation of means-testing for childrearing allowances and childcare subsidies from 2023. | Plausible match, but needs direct survey evidence on income-cap perceptions. |
| Installment design may reduce perceived usefulness. | Agent 2 recommended replacing the 3-year installment structure with immediate support or recurring tax credits. | I did not find a direct benchmark on installment vs. lump-sum fertility subsidy design in the first pass. | Unvalidated. Keep as a Prism-generated hypothesis. |

## Interpretation

The fertility demo passes a first directional validity check. Prism's main
findings are consistent with external evidence in three important ways:

1. Housing affordability is a credible fertility barrier in Taiwan.
2. Childcare and work-family balance are central policy levers.
3. Cash-only fertility incentives are usually weaker than broader structural
   family-support packages.

This improves the project because it lets us say:

> Prism recovered the same broad bottlenecks emphasized by Taiwan policy sources
> and international fertility-policy research: housing burden, childcare/work
> reconciliation, and the limited effect of cash-only subsidies.

The result should still be framed carefully. Prism is directionally useful, but
the current demo does not estimate real-world birth-rate effects or exact public
approval rates.

## Recommended Slide/Table Version

| Prism finding | Real-world support | Conclusion |
|---|---|---|
| NT$200,000 cash alone is too weak. | OECD/IMF evidence: cash transfers have limited or modest fertility effects. | Valid directional signal. |
| Housing cost dominates young-couple concerns. | Taiwan Legislative Yuan and OECD both identify housing cost as fertility-relevant. | Valid directional signal. |
| Childcare/work-family policies should be prioritized. | Taiwan NDC plan and OECD evidence emphasize childcare and work-family balance. | Valid directional signal. |
| Income cap and installments may create backlash. | Some support for broader eligibility, but limited direct evidence. | Treat as hypothesis for field testing. |

## Next Validation Step

For the final version of the project, run a stronger validation pass:

1. Re-run the fertility case with `n_per_cell = 20` or higher.
2. Run 3 prompt variants of the same policy description.
3. Check whether the same top barriers appear across runs:
   - housing cost
   - childcare cost/access
   - career/work-family conflict
   - insufficiency of cash-only support
4. Add a small stability table showing whether each finding appears in all runs.

This would move the project from "face-valid demo" toward a more defensible
simulation methodology.

## Sources

- Taiwan Legislative Yuan, "Analysis of High Housing Prices and Low Fertility"
  (`高房價對少子化問題之研析`), 2021:
  https://www.ly.gov.tw/Pages/Detail.aspx?nodeid=6590&pid=206972
- Taiwan National Development Council evidence platform, "Recent Revision
  Direction of Taiwan's Low-Birth-Rate Countermeasure Plan (2018-2024)", 2023:
  https://ebp.ndc.gov.tw/%E6%88%91%E5%9C%8B%E5%B0%91%E5%AD%90%E5%A5%B3%E5%8C%96%E5%B0%8D%E7%AD%96%E8%A8%88%E7%95%AB%EF%BC%88107%E5%B9%B4%E8%87%B3113%E5%B9%B4%EF%BC%89%E8%BF%91%E6%9C%9F%E4%BF%AE%E6%AD%A3%E6%96%B9%E5%90%91/
- Taiwan National Council for Sustainable Development / Ministry of the
  Interior news release on housing support for marriage and childrearing
  families, 2026:
  https://ncsd.ndc.gov.tw/Fore/News_detail/9d0db1dc-0b33-45b3-98b7-56c3bf78cef2
- OECD, "Fertility trends across the OECD: Underlying drivers and the role for
  policy", Society at a Glance 2024:
  https://www.oecd.org/en/publications/society-at-a-glance-2024_918d8db3-en/full-report/fertility-trends-across-the-oecd-underlying-drivers-and-the-role-for-policy_770679b8.html
- IMF, "Japan's Fertility: More Children Please", IMF Staff Country Report
  2024/119:
  https://www.elibrary.imf.org/view/journals/002/2024/119/article-A002-en.xml
