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

Cap & Floor Window 1 (PCR decision). Revenue inputs go to:
- File: `iFA2CFFM2_PCR_decision.xlsm` (authoritative Ofgem model)
- Sheet: `Costs & Revenue`, row 29 (ARt — assessed revenue, £m nominal)
- Column 16 = operational year 1 (calendar 2021) through column 40 = year 25 (2045)

Three copies written (P10 / P50 / P90 scenario revenues). Open in Excel —
Assessment sheet recalculates cap/floor breach automatically.

Section 19 reads cap/floor directly from `Revenue Adjustment` rows 11–12 of the same
file and computes breach probabilities from the MC distribution.
