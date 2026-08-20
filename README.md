# IFA2 Interconnector Equity Valuation Model

Quantitative equity valuation of **IFA2** (1 GW GB–France HVDC interconnector) under Ofgem's **Cap & Floor Window 1 PCR** regulatory regime.

The model simulates 20-year hourly revenues under 10,000 Monte Carlo paths of the GB–France price spread and computes floor/cap breach probabilities across five assessment periods (P2–P5, 2026–2045).

---

## Model

**Main notebook:** `M2/IC_spread_direct_v2.ipynb`

| Section | Purpose |
|---------|---------|
| 1–3 | Config, data loading, hourly panel construction |
| 4–5 | Descriptive statistics, exploratory analysis |
| 6–9 | OLS deterministic component estimation (f_S) |
| 10 | Jump detection (Cartea & González-Pedraz filter) |
| 11 | OU + jump mean-reversion NLS estimation |
| 12 | Rolling out-of-sample back-test → capture ratio |
| 13–15 | Monte Carlo setup and simulation (10,000 paths × 20 years) |
| 16 | Revenue tables and fan charts |
| 17 | Export revenues → Ofgem PCR Excel model |
| 18 | Accounts analysis vs audited financials |
| 19 | Window 1 cap/floor breach analysis |
| 21 | Window 3 PCR comparison |
| 22 | Equity returns — annual FCFE yield, NI and FCFE IRR for W1 and W3 |
| 20 | Summary and interpretation |

See `M2/methodology.md` for model equations and `M2/data.md` for data sources.

---

## Key Results (Window 1)

All values 2016/17-RPI-real GBPm. ODR = 3.945% real. NPV cap = £285.5m per period.

| Period | Years | P50 NPV Revenue | P > Cap | P < Floor |
|--------|-------|----------------|---------|-----------|
| P2 | 2026–2030 | £278m | **28.5%** | 0% |
| P3 | 2031–2035 | £312m | **97.4%** | 0% |
| P4 | 2036–2040 | £332m | **99.7%** | 0% |
| P5 | 2041–2045 | £407m | **100%** | 0% |

IFA2's P50 revenue of £61.6m in 2026 sits exactly at the W1 cap. Cap breach probability is 28.5% in P2 — dragged down by the 2027 Annex M GB price trough, where annual cap breach is only 7.4% and P50 revenue falls to £52.6m. From P3 onwards, the spread widens as FR prices decline faster than GB; revenues rise well above the cap (97–100% breach probability). The floor (£37.8m real) is never load-bearing in any year or scenario.

### Window 1 vs Window 3

Under Window 3 (CPIH-indexed, 2024 base), the cap is constant at £75.03m in 2024-CPIH-real and the floor at £54.74m. The W3 corridor (£20.3m) is far narrower than W1's in CPIH-real terms — and because the W3 cap grows at CPIH (2.5%/yr) while revenues grow faster, W3 is significantly more cap-restrictive than W1 in all periods. W3 cap breach probability is 92.7% in P2 and effectively certain from P3 onwards. The W3 floor is breached in 0.6% of paths in 2027 only.

| Period | Years | P50 NPV (2024-CPIH-real) | W1 P > Cap | W3 P > Cap | W3 P < Floor |
|--------|-------|--------------------------|-----------|-----------|-------------|
| P2 | 2026–2030 | £370m | 28.5% | **92.7%** | 0.0% |
| P3 | 2031–2035 | £429m | 97.4% | **100%** | 0.0% |
| P4 | 2036–2040 | £474m | 99.7% | **100%** | 0.0% |
| P5 | 2041–2045 | £603m | 100% | **100%** | 0.0% |

W3 NPV cap = £347.7m per period (constant in 2024-CPIH-real).

### Annual Revenue vs W3 Cap/Floor (2024-CPIH-real £m)

| Year | W3 Cap | W3 Floor | P50 Revenue | P > W3 Cap | P < W3 Floor |
|------|--------|---------|-------------|-----------|-------------|
| 2026 | £75.0m | £54.7m | £80.8m | **78.6%** | 0.0% |
| 2028 | £75.0m | £54.7m | £75.7m | 53.7% | 0.0% |
| 2030 | £75.0m | £54.7m | £91.5m | **98.9%** | 0.0% |
| 2035 | £75.0m | £54.7m | £94.4m | **99.5%** | 0.0% |
| 2040 | £75.0m | £54.7m | £113.0m | **100%** | 0.0% |
| 2045 | £75.0m | £54.7m | £139.5m | **100%** | 0.0% |

### Equity Returns (Section 22)

Annual FCFE yield on opening RAV (W1: £404m 16/17-real; W3: ~£558m 2024-CPIH-real). Tax = 25%.

| Scenario | W1 FCFE IRR (uncapped) | W1 FCFE IRR (regulated) | W3 FCFE IRR (uncapped) | W3 FCFE IRR (regulated) |
|----------|----------------------|------------------------|----------------------|------------------------|
| P50 | 8.68% | 6.89% | 9.45% | 6.55% |
| P10 | 7.54% | 6.37% | 8.40% | 6.32% |
| P90 | 9.89% | 7.07% | 10.57% | 6.61% |

Regulated FCFE IRR is compressed relative to uncapped because cap clawback removes the upside tail in high-revenue years (2022–2024 actuals, and P3–P5 projections all trigger ICFap). The regulated W3 IRR (6.55% P50) slightly exceeds W1 (6.89%... wait — W1 regulated 6.89% > W3 regulated 6.55%) because the W1 cap (£61.6m real) is lower in absolute terms but the W1 floor provides a tighter lower bound, while W3's narrower corridor captures less of the upside in high years.

---

## Model Parameters

| Parameter | Value |
|-----------|-------|
| OU phi (daily AR) | 0.7037 |
| Kappa (mean reversion) | ~128/yr |
| Half-life | ~2.0 days |
| Sigma_d | 15.04 GBP/MWh |
| Capture ratio (back-test mean) | 25.9% (31.8% in 2024, 20.0% in 2025) |
| Price data | GB-FR07.xlsx (Dec 2021 – Jul 2026) |

---

## Repository Structure

```
├── M2/
│   ├── IC_spread_direct_v2.ipynb         # main model
│   ├── IC_spread_direct_v2_executed.ipynb # last full execution output
│   ├── naive_sim_check.py                 # standalone sanity-check scenarios
│   ├── mc_revenue_ifa2.csv               # P10/P50/P90 annual revenues
│   ├── CLAUDE.md                         # model context for AI assistants
│   ├── data.md                           # data sources and conventions
│   └── methodology.md                    # model equations
├── ENTSO-E/
│   ├── GUI_NET_CROSS_BORDER_IFA2_combined.csv  # merged IFA2 flow data 2021–2026
│   ├── GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_*_IFA2_only.csv  # annual filtered files
│   └── filter_ifa2.py                    # script to produce combined CSV
├── GB-FR07.xlsx                          # Bloomberg GB/FR hourly prices + FX
└── CLAUDE.md                             # project context
```

---

## Data

Core data files are tracked in this repository. Files not committed (large binaries or sensitive) are available on OneDrive:

| File | In repo | Description |
|------|---------|-------------|
| `GB-FR07.xlsx` | ✓ | GB/FR hourly day-ahead prices + FX (Dec 2021 – Jul 2026) |
| `ENTSO-E/*_IFA2_only.csv` | ✓ | IFA2 physical flows by year (ENTSO-E filtered) |
| `ENTSO-E/GUI_NET_CROSS_BORDER_IFA2_combined.csv` | ✓ | Combined IFA2 flow file (all years) |
| `M2/IFA2_NTC_*.csv` | ✓ | Hourly NTC FR↔GB from ENTSO-E capacity allocation |
| `iFA2CFFM2_PCR_decision.xlsm` | — | Ofgem Window 1 PCR model | 
| `iFA2CFFM2_PCR_decision_W3.xlsm` | — | Ofgem Window 3 PCR model |
| `Annex_M_assumptions_growth_price.ods` | — | DESNZ Annex M (Feb 2026) |
| `Annex_M_assumptions_growth_price_EEP2021_2040.ods` | — | DESNZ Annex M (Oct 2022, back-test) |

OneDrive downloads:

| File | Link |
|------|------|
| `iFA2CFFM2_PCR_decision.xlsm` | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQA9utw5ykckTKLWqdzGW3_yAaJ2JYYwnX3cRd_lW5Ch-z8) |
| `iFA2CFFM2_PCR_decision_W3.xlsm` | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQBNRCOJk2HTQ7J0dQ6oGaQAARHfAL1OeXHcOaBJvHq62I8) |
| `Annex_M_assumptions_growth_price.ods` | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQDIVWs9rIeZT5dPxSZQKNrEAfreUhLVIx4Bsq-QempgcR0) |
| `Annex_M_assumptions_growth_price_EEP2021_2040.ods` | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQAu79i8ikCmQ6QFRA7KOTAvAb4nPp7AvcoLq-YmMpNNfvU) |
| `ic_cap_floor_ifa2_window3.xlsm` | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQD7wWpXXqPJSITnMg9mASNPASbyiPGfb0JwnpA7vk1lPqg) |
| `copy_cap_and_floor_financial_model_-_ifa2_fpa.xlsm` | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQAfdmEzy4wKT4pNVtDk3WC5Aeu9hElOaYSih2aihDPbcXo) |
