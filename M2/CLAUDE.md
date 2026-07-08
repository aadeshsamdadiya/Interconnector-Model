# IFA2 Interconnector — Spread-Direct OU Model

## Purpose

Equity valuation of IFA2 (1 GW GB–France HVDC) under Ofgem Cap & Floor (Window 1 PCR).
The model simulates 25-year hourly revenues under 10,000 Monte Carlo paths and computes
floor/cap breach probabilities against the PCR decision schedule.

**Working file:** `IC_spread_direct_v2.ipynb`
**Output directory:** `/Users/aadesh/Documents/IC/M2/`

---

## Model Structure

Sections run sequentially; each section depends on outputs from prior ones.

| Section | Purpose |
|---------|---------|
| 1–3 | Config, data load, hourly panel construction (GB/FR prices + FX) |
| 4–5 | Descriptive stats, ADF tests, exploratory charts |
| 6–9 | OLS deterministic component f_S(t,h) estimation |
| 10 | Jump detection (Cartea & González-Pedraz iterative filter) |
| 11 | OU + jump mean-reversion NLS estimation |
| 12 | Rolling out-of-sample back-test → capture ratio |
| 13 | MC setup: f_S projection (tau-frozen at anchor date) |
| 14 | Annex M price path parsing + spread adjustment arrays |
| 15 | Monte Carlo simulation (10,000 paths × 20 years) |
| 16 | Revenue tables and fan charts (three scenarios) |
| 17 | Export revenues → PCR decision Excel model |
| 18 | Accounts analysis — revenue waterfall vs audited financials |
| 19 | Cap/floor breach analysis from PCR decision schedule |
| 21 | Window 3 PCR comparison (2024-CPIH-real basis) |
| 22 | Equity returns — annual FCFE yield and IRR for W1 and W3 |

→ See [`methodology.md`](methodology.md) for model equations and parameter choices.
→ See [`data.md`](data.md) for data sources, file paths, and conventions.

---

## Key Design Choices

**Spread modelled directly** (not log-prices). Revenue = |S_t| × capacity × availability
× capture ratio. Avoids Jensen's inequality bias that inflated revenues in the log-price
approach.

**Tau frozen at anchor date** in projection. The OLS linear trend is crisis-driven
(+9.45 GBP/MWh/yr over sample) and must not be extrapolated. f_S is frozen at the
March 2026 level; the Annex M spread adjustment (Section 14) handles all forward
price-level changes.

**Capture ratio** bridges gross spread revenue to net interconnector turnover. Estimated
out-of-sample from the back-test (Section 12) as audited turnover / simulated gross.
Accounts for explicit auction mechanism post-Brexit: IFA2 sells capacity in forward
auctions; the auction clearing price < realised spot spread; the residual is captured
by traders not IFA2.

**No Tobit censoring.** GB–France day-ahead market commits capacity the day before.
Operators cannot refuse individual hours. The censoring decision unit is the day (or
auction period), not the hour. Hourly censoring models a decision right that does not exist.

---

## Regulatory Framework

### Window 1 (PCR decision)

Revenue inputs go to:
- File: `iFA2CFFM2_PCR_decision.xlsm` (authoritative Ofgem model)
- Sheet: `Costs & Revenue`, row 29 (ARt — assessed revenue, £m nominal)
- Column 16 = operational year 1 (calendar 2021) through column 40 = year 25 (2045)

Three copies written (P10 / P50 / P90 scenario revenues). Open in Excel —
Assessment sheet recalculates cap/floor breach automatically.

Section 19 reads cap/floor directly from `Revenue Adjustment` rows 11–12 of the same
file and computes breach probabilities from the MC distribution.

**W1 cap/floor (16/17-RPI-real):** cap = £61.6m, floor = £37.8m.

### Window 3 (Section 21)

- File: `iFA2CFFM2_PCR_decision_W3.xlsm` — Inputs sheet
- **Cap = PCL + PCAC = £71.042m + £3.989m = £75.031m** (2024-CPIH-real, constant)
- **Floor = PFL + PCAF = £45.604m + £9.136m = £54.740m** (2024-CPIH-real, constant)
- Corridor = £20.29m
- Cap return rate: 7.42% real; Floor return rate: 3.55% real
- OPEX (2024-CPIH-real): controllable from Inputs row 35, non-controllable row 36
- W3 RAV approximated as W1_RAV × RPIt / CPIHt (Op RAV sheet not in W3 model)

**W3 breach probabilities (2024-CPIH-real basis, 5-year NPV):**

| Period | Years | P > W3 Cap | P < W3 Floor |
|--------|-------|-----------|-------------|
| P2 | 2025–2029 | 99.8% | 0.0% |
| P3 | 2030–2034 | 18.2% | 0.0% |
| P4 | 2035–2039 | 27.6% | 0.0% |
| P5 | 2040–2044 | 96.6% | 0.0% |

Cap binds heavily in P2/P5; P3/P4 revenues mostly within corridor. Floor never load-bearing at P50.

### Equity Returns (Section 22)

Investment base includes IDC capitalised during 2016–2021 construction (Opening Op RAV yr1).
FCFE = Net income + Dep − Replacement capex. Tax = 25%.

| Scenario | W1 FCFE IRR (regulated) | W3 FCFE IRR (regulated) |
|----------|------------------------|------------------------|
| P50 | 5.90% | 6.39% |
| P10 | 4.69% | 5.59% |
| P90 | 6.89% | 6.61% |

W1 investment base: £404m (16/17-real). W3 investment base: ~£558m (2024-CPIH-real, approx).
Chart output: `equity_returns_fcfe.png`.
