# CLAUDE.md — IFA2 Interconnector Equity Valuation

This file provides guidance to Claude Code when working in this repository.

## Current Model

**Working directory:** `M2/`
**Working file:** `M2/IC_spread_direct_v2.ipynb`
**Specification files:** `M2/CLAUDE.md`, `M2/methodology.md`, `M2/data.md`

The M2 model supersedes all earlier scripts (`IC_descriptive_stats.ipynb`,
`aquind_descriptive_stats.py`, `aquind_descriptive_stats.ipynb`) which modelled
GB and FR log-prices separately. The M2 model operates directly on the GB−FR spread.

→ For full model specification, design choices, and Excel layouts, read `M2/CLAUDE.md` first.

---

## Repository Layout

```
M2/                              # active model
  IC_spread_direct_v2.ipynb      # main notebook (§1–22)
  CLAUDE.md                      # architecture guide
  methodology.md                 # mathematical specification
  data.md                        # data sources, config values, file paths
  equity_returns.py              # standalone equity returns script
  acf_check.py                   # diagnostic: ACF of OU residuals
  acf_results.md                 # ACF findings (long memory, GARCH effects)

IFA2CFFM1_PCR_decision.xlsm     # W1 cost model (OPEX, Dep, RAV for §22)
IFA2CFFM1_PCR_decision_W3.xlsm  # W3 cost model
iFA2CFFM2_PCR_decision_W3.xlsm  # W3 cap/floor model (PCL, PFL, PCAC, PCAF)
README.md                        # project summary and key results snapshot
```

Data files (large binaries, not git-tracked): `GB-FR07.xlsx`, Annex M `.ods` files,
`iFA2CFFM2_PCR_decision.xlsm`. Download links in `README.md`.

---

## Regulatory Context

**Cap & Floor Window 1 (PCR decision):** Ofgem guarantees a revenue floor (ICFar support)
and caps upside (ICFap clawback) over five 5-year assessment periods (2020–2044).
IFA2 operational year 1 = 2021; regime runs 25 years to 2045.

**Cap & Floor Window 3:** Same structure, CPIH-indexed from a 2024 base rather than
RPI-indexed. Cap and floor levels read from `iFA2CFFM2_PCR_decision_W3.xlsm` Inputs sheet
(PCL row 25, PFL row 26, PCAC row 27, PCAF row 28, col I). Re-read from Excel whenever
parameters change — do not rely on any hardcoded values in documentation.

**Key distinction:** W1 cap/floor rise over time in real terms (RPI > CPIH); W3 cap/floor
are constant in 2024-CPIH-real. Cross-convert W1 revenues: `rev_cpih = rev_1617 × RPIt / CPIHt`.

---

## Python Environment

```
/opt/homebrew/bin/python3.11
Key packages: pandas, numpy, scipy, statsmodels, matplotlib, openpyxl
Jupyter kernel: Python 3.11 (Homebrew) in VS Code
```
