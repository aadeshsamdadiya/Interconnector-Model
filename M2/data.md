# Data Sources and File Conventions

## Price Data

| Source | Path | Content |
|--------|------|---------|
| GB prices | `IC/Cleaned_GBFR.xlsx` → `GB_FINAL` | N2EX day-ahead hourly, GBP/MWh |
| FR prices | `IC/Cleaned_GBFR.xlsx` → `FR_FINAL` | EPEX day-ahead hourly, EUR/MWh |
| FX | `IC/Cleaned_GBFR.xlsx` → `GBP-EUR` | Bloomberg EURGBP daily |
| ENTSO-E flows | `~/Downloads/GUI_NET_CROSS_BORDER_IFA2_combined.csv` | IFA2 physical flows 2022–2025 |

**Format:** GB/FR sheets are (N_days × 24) with columns H01–H24. The `_wide_to_hourly()`
function in Section 2 reshapes to a proper DatetimeIndex hourly series.

**FX convention:** `FR_price_GBP = FR_price_EUR × fx_eur_gbp` (multiply, EUR→GBP rate).

---

## Forward Price Scenarios

| Source | Path | Content |
|--------|------|---------|
| Annex M (Feb 2026) | `~/Downloads/Annex_M_assumptions_growth_price.ods` | DESNZ GB wholesale scenarios |
| Annex M (Oct 2022) | `~/Downloads/Annex_M_assumptions_growth_price_EEP2021_2040.ods` | Prior vintage for validation |

Annex M units: p/kWh real 2024. Parser multiplies by 10 → GBP/MWh.
Sheets: `Reference`, `FFP_Low`, `FFP_High` (and `FFP_Exten_High` in Oct 2022 vintage).

FR price nodes (RTE Bilan Prévisionnel 2025 + ENTSO-E ERAA 2024): hardcoded in Section 14
as `_FR_NODES_EUR_25` dict, linearly interpolated between node years.

---

## Regulatory Model

| File | Purpose |
|------|---------|
| `IC/iFA2CFFM2_PCR_decision.xlsm` | Ofgem PCR decision cap/floor model (authoritative) |

Revenue write target: `Costs & Revenue` sheet, row 29 (ARt), columns 16–40 (op years 1–25).
Cap/floor read source: `Revenue Adjustment` sheet, rows 11–12 (CLt and FLt).
Section 19 also reads the operational discount rate from `Assessment` row 13.

Three output copies written to `M2/`: `ifa2_pcr_p10.xlsm`, `ifa2_pcr_p50.xlsm`, `ifa2_pcr_p90.xlsm`.

---

## IFA2 Audited Financials

Hardcoded in config as `ACTUALS` dict (£m nominal turnover from Ofgem annual compliance
assessments). Source files:

| Year | Path |
|------|------|
| 2022 | `~/Downloads/IFA2 - 2022.xlsx` |
| 2023 | `~/Downloads/IFA2 - 2023.xlsx` |
| 2024 | `~/Downloads/IFA2 - 2024 Statements.xlsx` |
| 2025 | `~/Downloads/IFA2-2025 Statements.xlsx` |

Values kept hardcoded (not parsed) — four final numbers, fragile to parse from Excel.

---

## Conventions

- **Spread sign:** GB − FR (positive = GB more expensive = FR→GB flow profitable)
- **Revenue formula:** `|spread| × capacity_MW × availability × hours × capture_ratio`
- **Availability:** parameter in config (Ofgem target ~95.6%)
- **Projection period:** 20 years from `PROJ_START_YEAR` (set in Section 1 config)
- **Regime start:** calendar year 2021 (op year 1); regime runs 25 years to 2045
- **tau anchor:** March 2026 end-of-sample; f_S frozen here for all projection years
