# Data Sources — IFA2 Spread-Direct OU Model

All paths are absolute. Data files are not git-tracked (large binaries); download links in `/Users/aadesh/Documents/IC/README.md`.

---

## 1. Price Data — `GB-FR07.xlsx`

Path: `/Users/aadesh/Documents/IC/GB-FR07.xlsx`

| Sheet | Content | Units |
|-------|---------|-------|
| `GB_FINAL` | GB N2EX day-ahead prices | GBP/MWh; wide format N_days × 24 (cols H01–H24) |
| `FR_FINAL` | FR EPEX day-ahead prices | EUR/MWh; same wide format |
| `GBP-EUR` | Bloomberg EURGBP daily FX | Column "EUR/GBP" = GBP per 1 EUR (multiply to convert) |

**Reshaping:** `_wide_to_hourly(df, value_col)` melts H01–H24 columns into a DatetimeIndex
hourly series. Date column is first column; hour suffix parsed as integer offset.

**FX convention:** `FR_price_GBP = FR_price_EUR × fx_eur_gbp` (multiply, NOT divide).
FX is daily; forward-filled to hourly to match price panel.

**Gap handling:** linear interpolation for gaps ≤ 4 consecutive hours; longer gaps dropped.
Panel aligned on inner join of GB and FR hourly indices.

**Sample:** Dec 2021 – Jul 2026 (extended dataset `GB-FR07`; earlier files end Mar 2026).

---

## 2. Forward Price Scenarios — Annex M

| Vintage | Path | Used for |
|---------|------|----------|
| Feb 2026 | `/Users/aadesh/Documents/IC/Annex_M_assumptions_growth_price.ods` | Live model (§14) |
| Oct 2022 | `/Users/aadesh/Documents/IC/Annex_M_assumptions_growth_price_EEP2021_2040.ods` | Back-test validation (§12, §14.1) |

**Parser (`_parse_annex_m`):** finds row where col A contains "baseload" (case-insensitive);
reads year headers from row 1; returns `{year: price}` dict. Engine: `odf`.
Units: p/kWh real 2024. Multiply by 10 → GBP/MWh.
Sheets used: `Reference`, `FFP_Low`, `FFP_High`.

**GB panel actuals used in scale factor** (hardcoded in §14, mean N2EX 2024–2025):
```python
PANEL_ACTUALS_GB = {2023: 107.89, 2024: 85.88, 2025: 94.34}  # GBP/MWh
```

**FR price nodes** (hardcoded in §14, EUR/MWh real 2025, linearly interpolated):
```python
_FR_NODES_EUR_25 = {
    'central':      {2026:52, 2028:50, 2030:62, 2032:70, 2035:80,  2038:87,  2040:92},
    'low_surplus':  {2026:48, 2028:44, 2030:50, 2032:55, 2035:62,  2038:66,  2040:68},
    'high_co2_gas': {2026:58, 2028:58, 2030:75, 2032:86, 2035:100, 2038:110, 2040:118},
}
```
Converted to GBP at `fr_anchor` (2024–25 panel mean FR price in GBP/MWh).
Node years: [2026, 2028, 2030, 2032, 2035, 2038, 2040]; extrapolated flat beyond 2040.

---

## 3. ENTSO-E Physical Flows

Path: `/Users/aadesh/Documents/IC/ENTSO-E/GUI_NET_CROSS_BORDER_IFA2_combined.csv`
(Also referenced from `~/Downloads/` in some cells — use IC/ENTSO-E/ version.)

Hourly net cross-border flow (MW), positive = FR→GB. Used in §5.1 (against-price analysis)
and §18 (GCR vs assessed revenue). Not used in Monte Carlo.

---

## 4. Config Parameters (§1)

All in Section 1 config cell. Change here; all downstream sections pick up automatically.

```python
REGIME_START    = 2021        # IFA2 Window 1 op year 1
PROJ_START_YEAR = 2026        # first year without a complete Ofgem actual
N_PROJ_YEARS    = 20          # 2026–2045 (total regime = 25 yrs: 2021–2045)
CAPACITY_MW     = 1_000       # interconnector capacity
AVAILABILITY    = 0.9659      # Ofgem target availability
N_PATHS         = 10_000      # Monte Carlo paths
RANDOM_SEED     = 42          # numpy RNG seed
PROJ_TAU_GROWTH = 0.0         # trend growth in projection (0 = frozen)
ANCHOR_DATE     = pd.Timestamp('2025-01-01')  # tau freeze point
```

**Audited actuals** (nominal turnover £m, from Ofgem compliance assessments):
```python
ACTUALS = {2022: 69.6, 2023: 100.8, 2024: 101.6, 2025: 72.2}
```
2021 not separately disclosed (commissioning/ramp-up year).

---

## 5. Window 1 Regulatory Excel — `iFA2CFFM2_PCR_decision.xlsm`

Path: `/Users/aadesh/Documents/IC/iFA2CFFM2_PCR_decision.xlsm`

| Sheet | Row | Col(s) | Content |
|-------|-----|--------|---------|
| `Costs & Revenue` | 29 | 16–40 | ARt — write assessed revenues here (nominal £m) |
| `Revenue Adjustment` | 5 | 1–45 | Op year labels (calendar year = 2020 + op_yr) |
| `Revenue Adjustment` | 11 | 1–45 | CLt — cap levels (nominal £m; deflate by RPIt for real) |
| `Revenue Adjustment` | 12 | 1–45 | FLt — floor levels (nominal £m) |
| `Indexation` | 5 | 1–45 | Year labels for RPIt index |
| `Indexation` | 11 | 1–45 | RPIt — RPI index multiplier (2016/17-real → nominal) |
| `Assessment` | 13 | — | ODR — operational discount rate (real) |

Columns 16–40 correspond to op years 1–25 (calendar 2021–2045).
ARt written as nominal: `ARt = rev_1617_real × RPIt[yr]`.
Actuals (ACTUALS dict, already nominal) written without conversion for yr < PROJ_START_YEAR.

---

## 6. Window 3 Regulatory Excel — `iFA2CFFM2_PCR_decision_W3.xlsm`

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

---

## 7. W1 Cost Model Excel — `IFA2CFFM1_PCR_decision.xlsm`

Path: `/Users/aadesh/Documents/IC/IFA2CFFM1_PCR_decision.xlsm`
Used in §22 (equity returns). Values hardcoded as arrays in §22 — re-extract if model updates.

| Sheet | Content | Used for |
|-------|---------|----------|
| `Allowances Cap` | OPEX (controllable + non-controllable), Depreciation | Annual P&L |
| `Op RAV` | Opening RAV yr1 (investment base incl. IDC), replacement capex schedule | FCFE |
| `Tax Cap` | Corporation tax | Note: model uses 19%; §22 overrides to 25% (current rate) |

W1 Opening Op RAV yr1 = investment base including IDC capitalised 2016–2021 construction.

---

## 8. CPIH Index Values

Used in W3 price basis conversions. Historical values hardcoded in §21:
```python
CPIH_HIST = {2019: 107.4, 2020: 108.0, 2021: 113.1,
             2022: 120.6, 2023: 126.1, 2024: 132.9}  # ONS L522, Jan 2015=100
CPIH_2024_BASE = 132.9
CPIH_GROWTH    = 0.025   # OBR medium-term projection beyond 2024
```
`CPIHt = CPIH_level[yr] / 132.9`; projected: `CPIH_level[yr] = 132.9 × 1.025^(yr−2024)`.

---

## 9. Output Files

All written to `/Users/aadesh/Documents/IC/M2/`:

| File | Content |
|------|---------|
| `ifa2_pcr_p{10,50,90}.xlsm` | W1 PCR model with P10/P50/P90 revenues in ARt row 29 |
| `ifa2_w3_pcr_p{10,50,90}.xlsm` | W3 PCR model with revenues in 2024-CPIH-real |
| `mc_revenue_spread_direct.csv` | P10/P50/P90 annual revenues (2016/17-real £m), 2026–2045 |
| `equity_returns_fcfe.png` | Annual FCFE yield chart, W1 and W3 |
| `fig_*.png` | EDA, methodology comparison, backtest, price trajectory charts |
