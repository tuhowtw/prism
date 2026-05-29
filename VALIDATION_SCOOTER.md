# Prism Scooter Demo: Benchmark Validation Note

## Purpose

This note checks whether the electric-scooter trade-in demo is directionally
consistent with external evidence. It does not prove that synthetic Prism
respondents predict real rider behavior. It helps separate supported findings
from hypotheses that should be tested with field data.

## Prism Run Used

- Run: `runs/20260528_220202_n3/manifest.json`
- Policy tested: NT$8,000 trade-in rebate for gasoline-scooter owners who switch
  to an electric scooter, with Gogoro/iRent as partners and a 6-month completion
  window.
- Segments:
  - Budget-Conscious Commuter
  - Skeptical Traditionalist
  - Urban Convenience Seeker
- Sample size: `n_per_cell = 3`, so this is a smoke-test run.
- Prism headline result: weighted reception score `1.95 / 5`.
- Prism key insight: the rebate is weak because riders worry about total cost,
  battery subscription dependence, infrastructure convenience, and deadline
  pressure.

## Benchmark Comparison

| Validation claim | Prism output | External benchmark | Assessment |
|---|---|---|---|
| NT$8,000 is a real policy-relevant amount, but likely not enough by itself. | Prism found the flat rebate was insufficient for price-sensitive riders. | Taiwan's Ministry of Economic Affairs material says buyers can receive up to NT$8,000 and the current program runs to 2026/12/10. The official electric-motorcycle subsidy site also lists central and local subsidies, including local add-ons that can exceed the central amount. | Directionally supported. NT$8,000 is realistic, but the existence of additional local subsidies supports the idea that central support alone may feel small. |
| Total cost of ownership is the central adoption barrier. | Budget-conscious riders focused on purchase price plus battery/service costs. | A Taiwan scooter lifecycle study found e-scooters can cost more to own than gasoline scooters in some comparisons, and that battery swapping shifts battery cost from upfront purchase into operating expense. | Strong directional match. |
| Battery-swapping convenience is a double-edged issue. | Some users cared about station accessibility; others disliked dependence on a proprietary network. | Gogoro reports a dense Taiwan network with over 2.7 thousand GoStation locations and over 665,000 monthly battery-swapping subscribers as of December 31, 2025. But Gogoro's own service agreement and annual report describe battery service as a subscription/tariff-plan model. | Supported, with nuance. Infrastructure is strong in Taiwan, but subscription dependence is a plausible concern. |
| Range and station access are credible concerns, but not necessarily fatal in dense cities. | Prism flagged station availability and range confidence as barriers. | Gogoro's 2025 annual filing lists limited range, station availability, service availability, and perceptions of convenience/speed/cost as market factors affecting ePTW adoption. Research on Taiwan battery swap stations found successful use and high acceptance in an experiment, suggesting good station UX can reduce friction. | Directionally supported. |
| Air quality and climate arguments are credible policy rationales, but may not drive conversion alone. | Environmental framing helped the receptive segment but did not overcome cost and convenience concerns. | Taiwan's Ministry of Environment says old-vehicle replacement and EV-related policies are part of air-quality and net-zero strategy. It also reports PM2.5 and NOx declines from 2017 to 2022 under broader air-quality policies. | Supported as policy rationale, but not enough to infer consumer conversion. |
| A strict 6-month completion window is a plausible friction point. | Prism said the deadline adds pressure and can discourage busy riders. | I did not find a direct benchmark on a 6-month scooter-swap deadline in the first pass. | Unvalidated. Treat as a Prism-generated hypothesis for field testing. |
| DIY repairability and distrust of proprietary service is plausible but needs direct survey evidence. | The Skeptical Traditionalist segment showed WTP of NT$0 and emphasized repair freedom. | Gogoro materials confirm a service/subscription ecosystem, but the first-pass sources do not directly measure Taiwanese gasoline-scooter riders' repairability concerns. | Plausible hypothesis, not validated. |

## Interpretation

The scooter demo passes a first directional validity check. The strongest
externally supported findings are:

1. A flat NT$8,000 incentive may be too weak if riders evaluate full ownership
   cost and battery/service expenses.
2. Battery-swapping infrastructure is a core adoption variable: it can solve
   range/time problems, but it also creates subscription dependence.
3. Environmental benefits are a credible government rationale, but the simulated
   conversion bottleneck is consumer economics and convenience.

The weaker findings are the exact 6-month deadline effect and the repairability
backlash. Keep those as hypotheses until tested with real users.

## Recommended Slide/Table Version

| Prism finding | Real-world support | Conclusion |
|---|---|---|
| NT$8,000 alone feels too weak. | MOEA lists NT$8,000 central support; local add-ons exist, implying larger incentive stacks are often needed. | Valid directional signal. |
| Total cost and battery fees matter. | Taiwan lifecycle-cost research highlights ownership cost differences and battery swapping as operating expense. | Valid directional signal. |
| Swapping station convenience matters. | Gogoro has dense infrastructure, and research shows station UX affects acceptance. | Valid directional signal. |
| Subscription dependence is a concern. | Gogoro's model includes tariff plans and recurring battery-swapping subscriptions. | Plausible and important. |
| 6-month deadline stress matters. | No direct benchmark found. | Treat as hypothesis. |

## Recommended Next Validation Step

Run a small stability test with three scooter-policy prompt variants:

1. Neutral: current wording.
2. Optimistic: emphasize air quality, convenience, and existing GoStation density.
3. Skeptical: emphasize monthly battery plans, repairability, and deadline burden.

Track whether the same findings appear:

- total cost after rebate
- battery subscription concern
- station access / swapping convenience
- deadline stress
- current-scooter satisfaction

For a presentation, `n_per_cell = 5` is acceptable. For a stronger report, use
`n_per_cell = 10` or higher and compare repeated findings across variants.

## Sources

- Ministry of Economic Affairs Green Energy Industry Promotion Center,
  "購買電動機車補助再享汰舊換新加碼1000元，最高可享補助8000元", 2025:
  https://service.moea.gov.tw/EE514/tw/geipc/155-6587.html
- Electric Motorcycle Industry Upgrade and Low-Carbon Promotion Plan,
  official subsidy information page, updated 2026/05/07:
  https://meid.nat.gov.tw/lev/subsidy/city
- Ministry of Environment, "Policies to Retire Old Motorcycles Improve Air
  Quality by 30%", 2023:
  https://www.moenv.gov.tw/en/news/press-releases/3867.html
- Gogoro Network Smart Battery Service Agreement, version July 2025:
  https://network.gogoro.com/tw/en/contract/battery-contract/
- Gogoro Inc. Form 20-F annual report for fiscal year 2025, filed 2026/03/31:
  https://investor.gogoro.com/static-files/a62d545d-bff6-41b0-beac-1317b4fe6522
- "Beyond personal vehicles: How electrifying scooters will help achieve climate
  mitigation goals in Taiwan", Transportation Research Part D, 2023:
  https://www.sciencedirect.com/science/article/pii/S2211467X23000068
- "Understanding user acceptance of battery swapping service of sustainable
  transport: An empirical study of a battery swap station for electric scooters,
  Taiwan", International Journal of Sustainable Transportation, TRID record:
  https://trid.trb.org/View/1682273
