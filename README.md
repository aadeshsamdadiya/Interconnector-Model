# IFA2 Interconnector Equity Valuation Model

Quantitative equity valuation of **IFA2** (1 GW GB–France HVDC interconnector) under Ofgem's **Cap & Floor Window 1 PCR** regulatory regime.

The model simulates 25-year hourly revenues under 10,000 Monte Carlo paths of the GB–France price spread and computes floor/cap breach probabilities across five assessment periods (2025–2044).

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
| 20 | Summary and interpretation |
| 21 | Window 3 PCR comparison |

See `M2/methodology.md` for model equations and `M2/data.md` for data sources.

---

## Key Results (Window 1)

All values 2016/17-RPI-real GBPm. ODR = 3.945% real.

| Period | Years | P50 NPV Revenue | P > Cap | P < Floor |
|--------|-------|----------------|---------|-----------|
| P2 | 2025–2029 | £293.5m | **76.4%** | 0% |
| P3 | 2030–2034 | £243.5m | 0.1% | 0% |
| P4 | 2035–2039 | £238.4m | 0.0% | 0% |
| P5 | 2040–2044 | £256.8m | 1.2% | 0% |

IFA2 is cap-heavy in P2 — early revenues (~£78.5m P50 in 2026) exceed the real cap of £61.6m. Revenue mean-reverts into the corridor (cap £61.6m, floor £37.8m) from P3 onwards. Floor is never load-bearing at P50.

### Window 1 vs Window 3

Under Window 3 (CPIH-indexed, 2024 base), the cap is constant at £79.9m in 2024-CPIH-real but does not rise with RPI — creating a second cap-heavy period in P5 (67.3% breach probability vs 1.2% under Window 1).

| Period | W1 P > Cap | W3 P > Cap |
|--------|-----------|-----------|
| P2 | 76.1% | **87.8%** |
| P3 | 0.1% | 1.6% |
| P4 | 0.0% | 3.2% |
| P5 | 1.2% | **67.3%** |

---

## Model Parameters

| Parameter | Value |
|-----------|-------|
| OU phi (daily AR) | 0.715 |
| Kappa (mean reversion) | 122.8/yr |
| Half-life | 2.1 days |
| Sigma_d | 14.99 GBP/MWh |
| Capture ratio (back-test mean) | 25.9% |
| Price data | GB-FR07.xlsx (Dec 2021 – Jul 2026) |

---

## Repository Structure

```
├── M2/
│   ├── IC_spread_direct_v2.ipynb    # main model
│   ├── CLAUDE.md                    # model context for AI assistants
│   ├── data.md                      # data sources and conventions
│   └── methodology.md               # model equations
├── docs/
│   ├── academic/                    # Abadie & Chamorro (2021), Cartea (2012)
│   └── regulatory/                  # Ofgem W3 decision, ESO report, handbook
└── CLAUDE.md                        # project context
```

---

## Data

Data files are not tracked in this repository (large binaries). Download from OneDrive:

| File | Description | Link |
|------|-------------|------|
| `GB-FR07.xlsx` | GB/FR hourly day-ahead prices + FX (Dec 2021 – Jul 2026) | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQDg133PG1FdRKv8BkIunqR8AUsF3k1mhKVryH6gPHFpRTQ) |
| `iFA2CFFM2_PCR_decision.xlsm` | Ofgem Window 1 PCR model | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQA9utw5ykckTKLWqdzGW3_yAaJ2JYYwnX3cRd_lW5Ch-z8) |
| `iFA2CFFM2_PCR_decision_W3.xlsm` | Ofgem Window 3 PCR model | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQBNRCOJk2HTQ7J0dQ6oGaQAARHfAL1OeXHcOaBJvHq62I8) |
| `Annex_M_assumptions_growth_price.ods` | DESNZ Annex M (Feb 2026) | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQDIVWs9rIeZT5dPxSZQKNrEAfreUhLVIx4Bsq-QempgcR0) |
| `Annex_M_assumptions_growth_price_EEP2021_2040.ods` | DESNZ Annex M (Oct 2022) | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQAu79i8ikCmQ6QFRA7KOTAvAb4nPp7AvcoLq-YmMpNNfvU) |
| `GUI_NET_CROSS_BORDER_IFA2_combined.csv` | IFA2 physical flows (ENTSO-E) | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQBXmytOA31ZSrbq0mcXFPoUAYmlVq7WS9zuvjdQJUgP8PA) |
| `ic_cap_floor_ifa2_window3.xlsm` | IFA2 Cap & Floor model (Window 3 basis) | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQD7wWpXXqPJSITnMg9mASNPASbyiPGfb0JwnpA7vk1lPqg) |
| `copy_cap_and_floor_financial_model_-_ifa2_fpa.xlsm` | IFA2 Cap & Floor financial model (FPA copy) | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQAfdmEzy4wKT4pNVtDk3WC5Aeu9hElOaYSih2aihDPbcXo) |
| `Modelitem-Window1oldbasis-Window3updatedbasis-Note.csv` | W1 vs W3 basis comparison note | [Download](https://1drv.ms/x/c/4f7beaefd2dddda4/IQAHhnsVGFLBRIlroXl16qztAeU7SQQoJebQqdT4SwPjSfg) |
