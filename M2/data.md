# Data Sources — IFA2 Spread-Direct OU Model

All paths are absolute. Data files are not git-tracked (large binaries); download links in `/Users/aadesh/Documents/IC/README.md`.

---

## 1. Price Data — `GB-FR07.xlsx`

Path: `/Users/aadesh/Documents/IC/GB-FR07.xlsx`

| Sheet | Content | Units |
|-------|---------|-------|
| `GB_FINAL` | GB N2EX day-ahead prices | GBP/MWh nominal; wide format N_days × 24 (cols H01–H24) |
| `FR_FINAL` | FR EPEX day-ahead prices | EUR/MWh nominal; same wide format |
| `GBP-EUR` | Bloomberg EURGBP daily FX | Two columns: [date, "EUR/GBP"]; "EUR/GBP" = GBP per 1 EUR (multiply to convert) |

**Reshaping:** `_wide_to_hourly(df, value_col)` renames `Unnamed: 0` → `date`, melts H01–H24, and computes `timestamp = date + timedelta(hours = int(col[1:]) − 1)`. Returns hourly DatetimeIndex series.

**FX convention:** `FR_price_GBP = FR_price_EUR × fx_eur_gbp` (multiply, NOT divide). FX is daily; `fx.reindex(full_date_range).ffill()` to fill weekends. Mapped to hourly panel via `panel.index.normalize()`.

**Gap handling:** Reindex to complete hourly grid; linear interpolation for gaps ≤ `SHORT_GAP_H = 4` consecutive hours; longer gaps dropped via `dropna()`. Panel = inner join of GB and FR hourly indices.

**RPI deflation:** Applied immediately after panel construction (before any OLS or estimation). See §5 below. `t0_spread = daily.index[0]` (first day of deflated daily series, ≈ Dec 2021) — this is the OLS τ reference date, **not** `ANCHOR_DATE`.

**Sample:** Dec 2021 – Jul 2026 (extended dataset `GB-FR07`; earlier files end Mar 2026).

---

## 2. Forward Price Scenarios — Annex M

| Vintage | Path | Used for |
|---------|------|----------|
| Feb 2026 | `/Users/aadesh/Documents/IC/Annex_M_assumptions_growth_price.ods` | Live model (§14) |
| Oct 2022 | `/Users/aadesh/Documents/IC/Annex_M_assumptions_growth_price_EEP2021_2040.ods` | Back-test only (§12, §14.1) |

**Parser `_parse_annex_m(sheet_df, price_type='baseload')` — Feb 2026 file:**
1. Scan rows 0–9 for the row where `col A.strip().lower() == 'metric'` → this is the header row.
2. Read year columns from the header row: any value parseable as integer in range 2001–2055.
3. Identify "Fuel" column (header row cell where value == "fuel").
4. Scan all rows for first row where fuel column contains "baseload" (case-insensitive).
5. Return `pd.Series({year: float(price)})`. Engine: `odf`.

Units after parsing: p/kWh real 2024 GDP-deflated. Multiply by 10 → GBP/MWh. Sheets used: `Reference`, `FFP_Low`, `FFP_High`.

**Oct 2022 Annex M — different row layout (back-test only):**
- Years at row index 2 (0-based), starting col 5.
- Prices at row index 14 (baseload row in EEP file).
- In 2022-GDP-real. Rebased to 2016/17-RPI-real using hardcoded GDP growth:
```python
_GDP_FROM_2022 = {2023: 0.069000, 2024: 0.040225, 2025: 0.031785, 2026: 0.016721}
```

**Price basis conversion (CRITICAL — Annex M is 2024-GDP-real, NOT CPI-real):**

Annex M note 15: prices use the GDP deflator. Model and cap/floor are in 2016/17-RPI-real. Apply `adj_t` to all projected prices (GB and FR) before use:

```
adj_t = GDP_cum_t × RPI_1617 / RPI_t

  GDP_cum_t = ∏(1 + GDP_deflator[y])  for y = 2025 .. t    ← from Annex M Reference sheet row index 6
  RPI_t, RPI_1617 = 264.992                                  ← from FPA_RPI table (§6 below)
```

Pre-compute and cache: `ADJ_FACTORS = {yr: adj_t(yr) for yr in range(2020, 2051)}`. GDP deflator rates for years beyond Annex M: default to 0.023. Applied to both GB and FR projections.

**GB panel actuals used in scale factor** (2016/17-RPI-real GBP/MWh, from deflated panel):
```python
PANEL_ACTUALS_GB = {2023: 107.89, 2024: 85.88, 2025: 94.34}
```
These are RPI-deflated panel observations — distinct from `ACTUALS` (nominal turnover £m).

**FR anchor FX:** `fx_eur_gbp_fwd = panel.loc['2024':'2025', 'fx_eur_gbp'].mean()` — 2024–25 panel mean FX rate. All FR EUR node values converted via this single rate then multiplied by adj_t.

**FR price nodes** (EUR/MWh; adj_t and fx applied at runtime — do not pre-convert):
```python
_FR_NODES_EUR_25 = {
    'central':      {2026:52, 2028:50, 2030:62, 2032:70, 2035:80,  2038:87,  2040:92},
    'low_surplus':  {2026:48, 2028:44, 2030:50, 2032:55, 2035:62,  2038:66,  2040:68},
    'high_co2_gas': {2026:58, 2028:58, 2030:75, 2032:86, 2035:100, 2038:110, 2040:118},
}
_FR_NODE_YEARS = [2026, 2028, 2030, 2032, 2035, 2038, 2040]
```
Linear interpolation between nodes; extrapolated flat beyond 2040.

---

## 3. Public Holiday Data — `Fixed_Public_Holidays_GB_France.xlsx`

Path: `/Users/aadesh/Downloads/Fixed_Public_Holidays_GB_France.xlsx`
Sheet: `Fixed Public Holidays`

**Required** for the `D_t` dummy (weekend + public holiday flag) in the OLS feature matrix. Without this file the D_t column cannot be constructed.

Columns include `Month`, `Day`, `GB` (Yes/No), `France` (Yes/No). Loading logic:
```python
def _make_holiday_dates(years, df, country_col):
    dates = set()
    for _, row in df[df[country_col] == 'Yes'].iterrows():
        for yr in years:
            dates.add(pd.Timestamp(yr, int(row['Month']), int(row['Day'])))
    return dates

panel_years = range(panel.index.year.min(), panel.index.year.max() + 1)
GB_HOLIDAYS = _make_holiday_dates(panel_years, hol_df, 'GB')
FR_HOLIDAYS = _make_holiday_dates(panel_years, hol_df, 'France')
```

`D_t = 1` if `dayofweek >= 5` OR date in `GB_HOLIDAYS` OR date in `FR_HOLIDAYS`, else 0.
Generated over both historical and projection year ranges.

---

## 4. ENTSO-E Physical Flows

Path: `/Users/aadesh/Documents/IC/ENTSO-E/GUI_NET_CROSS_BORDER_IFA2_combined.csv`

Hourly net cross-border flow (MW), positive = FR→GB. Used in §5.1 (against-price analysis) and §18 (GCR vs assessed revenue). **Not used in Monte Carlo.**

---

## 5. Historical RPI Deflation Values

Applied to nominal prices from `GB-FR07.xlsx` before OLS estimation. Source: FPA model Input sheet row 97 (CHAW, Jan 1987=100):

```python
_HIST_RPI = {
    2021: 310.794, 2022: 320.864, 2023: 331.260,
    2024: 341.993, 2025: 353.073, 2026: 364.513,
}
_RPI_1617 = 264.992   # FPA row 96: 2016/17 CHAW base

panel['gb_price_gbp'] *= _RPI_1617 / _HIST_RPI.get(panel.index.year, last_value)
panel['fr_price_gbp'] *= ...   # same deflator
panel['spread_gbp']   *= ...   # same deflator
```

If a panel year falls outside `_HIST_RPI`, use `_HIST_RPI[max(_HIST_RPI)]` (2026 value). These values overlap with the `FPA_RPI` table in §6 — for projection years, use `FPA_RPI`.

---

## 6. FPA_RPI Projection Table

Full annual RPI index (CHAW, Jan 1987=100) from FPA model Input sheet row 97. Used in:
1. `adj_t` denominator: converting Annex M 2024-GDP-real → 2016/17-RPI-real for all projection years
2. W1/W3 price basis conversions (§§19, 21, 22)
3. Deflating CLt/FLt from nominal to 2016/17-real in breach analysis

```python
FPA_RPI = {
    2009: 215.767, 2010: 226.475, 2011: 237.342, 2012: 244.675,
    2013: 251.733, 2014: 256.667, 2015: 259.433, 2016: 264.992,
    2017: 273.578, 2018: 282.442, 2019: 291.593, 2020: 301.040,
    2021: 310.794, 2022: 320.864, 2023: 331.260, 2024: 341.993,
    2025: 353.073, 2026: 364.513, 2027: 376.323, 2028: 388.516,
    2029: 401.104, 2030: 414.099, 2031: 427.516, 2032: 441.368,
    2033: 455.668, 2034: 470.432, 2035: 485.674, 2036: 501.410,
    2037: 517.655, 2038: 534.427, 2039: 551.743, 2040: 569.619,
    2041: 588.075, 2042: 607.129, 2043: 626.799, 2044: 647.108,
    2045: 668.074, 2046: 689.720, 2047: 712.067, 2048: 735.138,
}
RPI_BASE_1617 = 264.992
```

For years beyond the table maximum, use `FPA_RPI[max(FPA_RPI)]`. Also used as the `CFFM2_RPIt` series when the Excel value is missing.

---

## 7. Config Parameters (§1)

All in the Section 1 config cell. Change here; all downstream sections pick up automatically.

```python
REGIME_START    = 2021        # IFA2 Window 1 op year 1
PROJ_START_YEAR = 2026        # first year without a complete Ofgem actual
N_PROJ_YEARS    = 20          # 2026–2045 (total regime = 25 yrs: 2021–2045)
CAPACITY_MW     = 1_000       # interconnector capacity
AVAILABILITY    = 0.9659      # Ofgem target availability
N_PATHS         = 10_000      # Monte Carlo paths
RANDOM_SEED     = 42          # seed for np.random.default_rng (not np.random.seed)
PROJ_TAU_GROWTH = 0.0         # trend growth in projection (0 = frozen at zero)
ANCHOR_DATE     = pd.Timestamp('2025-01-01')  # in config but NOT used as OLS t0_spread
```

**Audited actuals** (nominal turnover £m, from Ofgem compliance assessments):
```python
ACTUALS = {2022: 69.6, 2023: 100.8, 2024: 101.6, 2025: 72.2}
```
2021 not separately disclosed (commissioning/ramp-up year). Written directly to W1/W3 Excel for years < PROJ_START_YEAR (already nominal; no RPIt conversion needed).

**ODR (hardcoded in §19):** `ODR = 0.03945` real (from CFFM2 Assessment sheet row 13).

---

## 8. Window 1 Regulatory Excel — `iFA2CFFM2_PCR_decision.xlsm`

Path: `/Users/aadesh/Documents/IC/iFA2CFFM2_PCR_decision.xlsm`

| Sheet | Row | Col(s) | Content |
|-------|-----|--------|---------|
| `Costs & Revenue` | 29 | 16–40 | ARt — write assessed revenues here (nominal £m) |
| `Revenue Adjustment` | 5 | 1–45 | Op year labels (op yr N → calendar year = 2020+N) |
| `Revenue Adjustment` | 11 | 1–45 | CLt — cap levels (nominal £m; deflate by RPIt for real) |
| `Revenue Adjustment` | 12 | 1–45 | FLt — floor levels (nominal £m; same deflation) |
| `Indexation` | 5 | 1–45 | Year labels for RPIt index |
| `Indexation` | 11 | 1–45 | RPIt — RPI index multiplier (2016/17-real → nominal) |
| `Assessment` | 13 | — | ODR — operational discount rate (real) |

Columns 16–40 correspond to op years 1–25 (calendar 2021–2045).
ARt written as nominal: `ARt = rev_1617_real × RPIt[yr]`.
Actuals (ACTUALS dict, already nominal) written without conversion for yr < PROJ_START_YEAR.
Three output copies: `ifa2_pcr_p10.xlsm`, `ifa2_pcr_p50.xlsm`, `ifa2_pcr_p90.xlsm`.

---

## 9. Window 3 Regulatory Excel — `iFA2CFFM2_PCR_decision_W3.xlsm`

Path: `/Users/aadesh/Documents/IC/iFA2CFFM2_PCR_decision_W3.xlsm`

| Sheet | Row | Col | Content |
|-------|-----|-----|---------|
| `Inputs` | 25 | I | PCL — Preliminary Cap Level (2024-CPIH-real £m) |
| `Inputs` | 26 | I | PFL — Preliminary Floor Level |
| `Inputs` | 27 | I | PCAC — Cap PCA adjustment (can be negative) |
| `Inputs` | 28 | I | PCAF — Floor PCA adjustment |
| `Inputs` | 35 | P–AN | Controllable OPEX, op yrs 1–25 (2024-CPIH-real £m) |
| `Inputs` | 36 | P–AN | Non-controllable OPEX, op yrs 1–25 |
| `Inputs` | 40 | I | Cap return rate (real %) |
| `Inputs` | 41 | I | Floor return rate (real %) |
| `Costs & Revenue` | 29 | 16–40 | ARt — write assessed revenues (2024-CPIH-real £m) |
| `Inputs` | 145 | 16–40 | CPIHt index — write alongside revenues |

cap = PCL + PCAC; floor = PFL + PCAF. **Re-read from Excel every time parameters change.**
W3 ARt written as 2024-CPIH-real: `ARt = rev_1617_real × RPIt / CPIHt`.
Op RAV sheet absent in W3 model — W3 RAV in §22 approximated as `W1_RAV × RPIt / CPIHt`.
Three output copies: `ifa2_w3_pcr_p{10,50,90}.xlsm`.

---

## 10. W1 Cost Model Excel — `IFA2CFFM1_PCR_decision.xlsm`

Path: `/Users/aadesh/Documents/IC/IFA2CFFM1_PCR_decision.xlsm`
Used in §22 (equity returns). Values hardcoded as 25-element arrays in §22 — re-extract if the cost model changes.

| Sheet | Content | Used for |
|-------|---------|----------|
| `Allowances Cap` | OPEX (controllable + non-controllable combined), Depreciation | Annual P&L |
| `Op RAV` | Opening RAV yr1 (investment base incl. IDC), replacement capex schedule | FCFE |
| `Tax Cap` | Corporation tax rate | Note: Excel uses 19%; §22 overrides to 25% (current UK rate) |

W1 Opening Op RAV yr1 = investment base including IDC capitalised over 2016–2021 construction.

---

## 11. CPIH Index Values

Used in W3 price basis conversions. Historical values hardcoded in §21:
```python
CPIH_HIST = {2019: 107.4, 2020: 108.0, 2021: 113.1,
             2022: 120.6, 2023: 126.1, 2024: 132.9}  # ONS L522, Jan 2015=100
CPIH_2024_BASE = 132.9
CPIH_GROWTH    = 0.025   # OBR medium-term projection beyond 2024
```
`CPIHt = CPIH_level[yr] / 132.9`; projected: `CPIH_level[yr] = 132.9 × 1.025^(yr−2024)`.

---

## 12. Output Files

All written to `/Users/aadesh/Documents/IC/M2/`:

| File | Content |
|------|---------|
| `ifa2_pcr_p{10,50,90}.xlsm` | W1 PCR model with P10/P50/P90 revenues in ARt row 29 |
| `ifa2_w3_pcr_p{10,50,90}.xlsm` | W3 PCR model with revenues in 2024-CPIH-real |
| `mc_revenue_spread_direct.csv` | P10/P50/P90 annual revenues (2016/17-real £m), 2026–2045 |
| `equity_returns_fcfe.png` | Annual FCFE yield chart, W1 and W3 |
| `fig_*.png` | EDA, methodology comparison, backtest, price trajectory charts |
