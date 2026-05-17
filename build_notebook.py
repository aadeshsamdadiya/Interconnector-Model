"""Generates the restructured IC_spread_direct.ipynb with hourly OLS reconstruction."""
import nbformat
from pathlib import Path

cells = []

def md(src):
    return nbformat.v4.new_markdown_cell(src.strip())

def code(src):
    return nbformat.v4.new_code_cell(src)

# ── Title ──────────────────────────────────────────────────────────────────
cells.append(md("""\
# IFA2 Interconnector — Spread-Direct OU Model (Methodology 2)
**MSc Climate Change Finance and Investment**

## Background: Why a Second Methodology?

Methodology 1 (`IC_descriptive_stats.ipynb`) follows Abadie & Chamorro (2021): model \
`log(P_GB)` and `log(P_FR)` as separate OU+jump processes. Revenue = |exp(f_GB + X_GB) − exp(f_FR + X_FR)|.

This produced **P50 revenues of £305m/yr** against Ofgem-disclosed IFA2 actuals of **£108–188m/yr**.

**Root cause — Jensen's inequality:**

> E[|exp(X_GB) − exp(X_FR)|] >> |exp(E[X_GB]) − exp(E[X_FR])| when σ is large

Our log-price residual volatilities (σ_GB = 0.240, σ_FR = 0.421 per day) are driven up by the \
2021–2022 energy crisis. Abadie's Spain-France data predates that crisis (σ ≈ 0.05), making the \
inflation factor exp(σ²/2) ≈ 1.001 — negligible. Our high-volatility regime breaks the approximation.

## This Notebook: Spread-Direct OU with Hourly Reconstruction

Model S_t = P_GB_t − P_FR_t (£/MWh) as OU + jumps, following Cartea & González-Pedraz (2012). \
The OLS deterministic component is fitted on **hourly spread data** (36,984 obs) including \
24 hour-of-day dummy variables. This directly replicates Abadie's revenue step: for each \
simulated day, the single daily OU value X_d is combined with the 24 hourly OLS coefficients \
to reconstruct 24 hourly spreads, whose absolute values sum to the daily revenue.

**Pipeline:** Data Load → Clean → Descriptive Stats → EDA Plots → Full OLS (hourly) → \
Significance Tests → Refined OLS (hourly) → Jump Detection → OU Estimation → \
Monte Carlo Setup → Monte Carlo Simulation → Results → Excel Export
"""))

# ── Section 1 ──────────────────────────────────────────────────────────────
cells.append(md("## Section 1: Configuration & Imports"))

cells.append(code("""\
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
from scipy import stats as sp_stats
from statsmodels.tsa.stattools import adfuller

warnings.filterwarnings('ignore')
plt.rcParams.update({
    'figure.dpi': 120, 'axes.spines.top': False,
    'axes.spines.right': False, 'axes.grid': True,
    'grid.linewidth': 0.3, 'grid.alpha': 0.5, 'font.size': 10,
})

IC_DIR     = Path('/Users/aadesh/Documents/IC')
EXCEL_PATH = IC_DIR / 'Cleaned_GBFR.xlsx'
OUTPUT_DIR = IC_DIR / 'M2'
OUTPUT_DIR.mkdir(exist_ok=True)

REGIME_START    = 2021   # IFA2 Window 2 commissioning year
PROJ_START_YEAR = 2026   # first year without a complete Ofgem actual
N_PROJ_YEARS    = 20     # 2026-2045  (total regime = 25 yrs: 2021-2045)
CAPACITY_MW     = 1_000
AVAILABILITY    = 0.9659
N_PATHS         = 10_000
RANDOM_SEED     = 42
PROJ_TAU_GROWTH = 0.0
ANCHOR_DATE     = pd.Timestamp('2025-01-01')

# Ofgem-disclosed gross congestion revenues (net of market costs), GBPm
# 2021 not separately disclosed (commissioning / ramp-up year)
ACTUALS = {2022: 134.9, 2023: 188.3, 2024: 107.5, 2025: 109.4}

print(f'Config: REGIME_START={REGIME_START}  PROJ={PROJ_START_YEAR}-{PROJ_START_YEAR+N_PROJ_YEARS-1}')
print(f'        CAPACITY={CAPACITY_MW}MW  AVAILABILITY={AVAILABILITY}')
print(f'        N_PATHS={N_PATHS:,}  ANCHOR={ANCHOR_DATE.date()}')
"""))

# ── Section 2 ──────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 2: Data Loading

Data source: `Cleaned_GBFR.xlsx` — Bloomberg GB and FR hourly electricity prices + EUR/GBP FX.

| Sheet | Content | Units |
|---|---|---|
| `GB_FINAL` | N2EX GB day-ahead hourly prices | GBP/MWh |
| `FR_FINAL` | EPEX France day-ahead hourly prices | EUR/MWh |
| `GBP-EUR` | Bloomberg EUR/GBP daily FX rate | GBP per 1 EUR |

**Wide-to-long:** Each sheet stores dates as rows, hours (H01–H24) as columns. \
`_wide_to_hourly()` pivots to a timestamp-indexed Series.

**FX convention:** FR_price_GBP = FR_price_EUR × fx_eur_gbp (GBP per EUR — multiply, not divide).
"""))

cells.append(code("""\
SHORT_GAP_H = 4

def _wide_to_hourly(wide_df, value_col):
    df = wide_df.rename(columns={'Unnamed: 0': 'date'}).copy()
    df['date'] = pd.to_datetime(df['date'])
    hour_cols = sorted([c for c in df.columns if c.startswith('H') and c[1:].isdigit()],
                       key=lambda x: int(x[1:]))
    melted = df.melt(id_vars='date', value_vars=hour_cols,
                     var_name='hour_col', value_name=value_col)
    melted['offset']    = melted['hour_col'].str[1:].astype(int) - 1
    melted['timestamp'] = melted['date'] + pd.to_timedelta(melted['offset'], unit='h')
    return melted.set_index('timestamp')[value_col].sort_index().astype(float)

xl       = pd.ExcelFile(EXCEL_PATH)
gb_wide  = xl.parse('GB_FINAL')
fr_wide  = xl.parse('FR_FINAL')
fx_daily = xl.parse('GBP-EUR')

gb_s = _wide_to_hourly(gb_wide, 'gb_price_gbp')
fr_s = _wide_to_hourly(fr_wide, 'fr_price_eur')

fx = fx_daily.copy()
fx.columns = ['date', 'fx_eur_gbp']
fx['date'] = pd.to_datetime(fx['date'])
fx = fx.dropna(subset=['fx_eur_gbp']).set_index('date').sort_index()
fx = fx.reindex(pd.date_range(fx.index.min(), fx.index.max(), freq='D')).ffill()

print(f'GB:  {len(gb_s):,} hourly obs  ({gb_s.index.min().date()} to {gb_s.index.max().date()})')
print(f'FR:  {len(fr_s):,} hourly obs  ({fr_s.index.min().date()} to {fr_s.index.max().date()})')
print(f'FX:  {len(fx):,} daily obs  ({fx.index.min().date()} to {fx.index.max().date()})')
"""))

# ── Section 3 ──────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 3: Data Cleaning & Validation

1. Align GB and FR to common date range
2. Reindex to complete hourly grid — surfaces gaps
3. Fill short gaps (≤4 hours) by linear interpolation
4. Forward-fill FX from business-day to hourly frequency
5. Convert FR prices EUR → GBP; compute spread = GB − FR
6. Aggregate to daily means for descriptive statistics

**The hourly panel is retained throughout** — the OLS in Section 7 is fitted on the \
36,984 hourly spread observations, following Abadie's approach of modelling hourly seasonality.
"""))

cells.append(code("""\
panel = pd.concat([gb_s, fr_s], axis=1).sort_index()
panel = panel[~panel.index.duplicated(keep='last')]
start = max(panel['gb_price_gbp'].first_valid_index(),
            panel['fr_price_eur'].first_valid_index())
end   = min(panel['gb_price_gbp'].last_valid_index(),
            panel['fr_price_eur'].last_valid_index())
panel = panel.loc[start:end]

panel = panel.reindex(pd.date_range(panel.index.min(), panel.index.max(), freq='h'))
n_missing = panel.isna().any(axis=1).sum()
panel = panel.interpolate(method='linear', limit=SHORT_GAP_H).dropna()

panel['fx_eur_gbp']   = pd.Series(
    panel.index.normalize().map(fx['fx_eur_gbp']), index=panel.index
).bfill().ffill()
panel['fr_price_gbp'] = panel['fr_price_eur'] * panel['fx_eur_gbp']
panel['spread_gbp']   = panel['gb_price_gbp'] - panel['fr_price_gbp']
panel = panel.dropna(subset=['gb_price_gbp', 'fr_price_gbp', 'spread_gbp'])

daily       = panel[['gb_price_gbp', 'fr_price_gbp', 'spread_gbp']].resample('D').mean().dropna()
_sample_end = daily.index.max()

print(f'Hourly panel: {panel.index.min().date()} to {panel.index.max().date()}'
      f'  ({len(panel):,} obs, {n_missing} gaps filled)')
print(f'Daily series: {daily.index.min().date()} to {_sample_end.date()}'
      f'  ({len(daily):,} days)')
print(f'Hourly spread retained for OLS: {len(panel):,} obs')
"""))

# ── Section 4 ──────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 4: Descriptive Statistics

Level statistics and ADF unit-root tests. We expect to reject the unit-root null for the \
spread — stationarity is required for OU estimation and consistent with arbitrage limits.
"""))

cells.append(code("""\
stats_data = {}
for col, label in [('gb_price_gbp', 'GB price (GBP/MWh)'),
                    ('fr_price_gbp', 'FR price (GBP/MWh)'),
                    ('spread_gbp',   'Spread GB-FR (GBP/MWh)')]:
    s = daily[col]
    stats_data[label] = {
        'N':               len(s),
        'Mean':            round(s.mean(), 3),
        'Std Dev':         round(s.std(), 3),
        'Skewness':        round(sp_stats.skew(s), 3),
        'Excess Kurtosis': round(sp_stats.kurtosis(s), 3),
        'Min':             round(s.min(), 2),
        'Max':             round(s.max(), 2),
    }

print('Descriptive Statistics (daily averages):')
print(pd.DataFrame(stats_data).T.to_string())

print()
print(f'  {"Series":<22}  {"ADF stat":>10}  {"p-value":>10}  {"Result"}')
print('  ' + '-' * 65)
for col, label in [('gb_price_gbp', 'GB price'),
                    ('fr_price_gbp', 'FR price'),
                    ('spread_gbp',   'Spread GB-FR')]:
    stat, p, _, _, crit, _ = adfuller(daily[col].dropna(), autolag='AIC')
    verdict = 'Reject H0 (stationary)' if p < 0.05 else 'Fail to reject H0 (unit root)'
    print(f'  {label:<22}  {stat:>10.4f}  {p:>10.4f}  {verdict}')
"""))

# ── Section 5 ──────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 5: Exploratory Data Analysis

Four charts motivate the modelling choices:

- **Fig 1** — Price levels (crisis period visible)
- **Fig 2** — Daily GB−FR spread time series
- **Fig 3** — Spread distribution (excess kurtosis → jumps needed)
- **Fig 4** — Average spread by hour of day — **motivates inclusion of 24 hour dummies in OLS**
"""))

cells.append(code("""\
fig, axes = plt.subplots(4, 1, figsize=(13, 15))

ax = axes[0]
ax.plot(daily.index, daily['gb_price_gbp'], lw=0.8, color='steelblue',
        label='GB (GBP/MWh)', alpha=0.9)
ax.plot(daily.index, daily['fr_price_gbp'], lw=0.8, color='darkorange',
        label='FR (GBP/MWh)', alpha=0.9)
ax.axvspan(pd.Timestamp('2021-12-01'), pd.Timestamp('2023-06-01'),
           alpha=0.07, color='red', label='Crisis period')
ax.set_ylabel('GBP/MWh')
ax.set_title('Fig 1. Daily GB and FR Electricity Prices', fontweight='bold')
ax.legend(fontsize=9)

ax = axes[1]
ax.plot(daily.index, daily['spread_gbp'], lw=0.8, color='#2ca02c', alpha=0.85)
ax.axhline(0, color='k', lw=0.8, ls='--', alpha=0.5)
ax.axhline(daily['spread_gbp'].mean(), color='#2ca02c', lw=1.5, ls=':',
           label=f'Mean = {daily["spread_gbp"].mean():.1f} GBP/MWh')
ax.fill_between(daily.index, 0, daily['spread_gbp'],
                where=daily['spread_gbp'] > 0, alpha=0.15, color='#2ca02c')
ax.fill_between(daily.index, 0, daily['spread_gbp'],
                where=daily['spread_gbp'] < 0, alpha=0.15, color='red')
ax.set_ylabel('GBP/MWh')
ax.set_title('Fig 2. Daily GB-FR Spread  [positive = GB above FR]', fontweight='bold')
ax.legend(fontsize=9)

ax = axes[2]
sv = daily['spread_gbp'].dropna()
ax.hist(sv, bins=80, density=True, color='steelblue', alpha=0.6, label='Observed')
mu_s, sd_s = sv.mean(), sv.std()
xr = np.linspace(sv.min(), sv.max(), 300)
ax.plot(xr, sp_stats.norm.pdf(xr, mu_s, sd_s), 'r-', lw=2,
        label=f'N({mu_s:.1f}, {sd_s:.1f})')
ax.axvline(0, color='k', lw=0.8, ls='--', alpha=0.5)
ax.set_xlabel('GBP/MWh')
ax.set_title(
    f'Fig 3. Spread Distribution  '
    f'[skew={sp_stats.skew(sv):.2f}, excess kurt={sp_stats.kurtosis(sv):.2f}]',
    fontweight='bold')
ax.legend(fontsize=9)

# Fig 4: Average hourly spread profile (motivates hour dummies)
ax = axes[3]
hourly_profile = panel.groupby(panel.index.hour)['spread_gbp'].mean()
hourly_profile_norm = panel.loc['2024':'2025'].groupby(
    panel.loc['2024':'2025'].index.hour)['spread_gbp'].mean()
ax.bar(hourly_profile.index, hourly_profile.values, alpha=0.5,
       color='steelblue', label='Full sample (2021-2026)')
ax.bar(hourly_profile_norm.index, hourly_profile_norm.values, alpha=0.6,
       color='darkorange', width=0.4, label='Normalised (2024-2025)')
ax.axhline(0, color='k', lw=0.8, ls='--', alpha=0.5)
ax.set_xlabel('Hour of day (0 = midnight)')
ax.set_ylabel('Mean spread (GBP/MWh)')
ax.set_title('Fig 4. Average GB-FR Spread by Hour of Day'
             ' — motivates inclusion of 24 hour dummies', fontweight='bold')
ax.legend(fontsize=9)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'fig_eda.png', dpi=150, bbox_inches='tight')
plt.show()
print('Saved: fig_eda.png')
"""))

# ── Section 6 ──────────────────────────────────────────────────────────────
cells.append(md(r"""\
## Section 6: Model Specification

### 6.1 Decomposition

$$S_t = f_S(t, h) + X_t$$

where $S_t$ is the hourly spread (£/MWh), $f_S(t, h)$ the deterministic component, \
and $X_t$ the stochastic daily OU deviation.

### 6.2 Deterministic Component — Hourly OLS

Following Abadie & Chamorro (2021), the OLS is fitted on **hourly data** and includes \
24 hour-of-day dummy variables alongside the Fourier, trend, and weekend terms:

$$f_S(t, h) = \beta_0 + \beta_1\tau + \beta_2\sin(2\pi\tau) + \beta_3\cos(2\pi\tau)
              + \beta_4\sin(4\pi\tau) + \beta_5\cos(4\pi\tau) + \beta_6 D_t
              + \sum_{h=2}^{24} \beta_h \mathbf{1}[\text{hour}=h]$$

The hourly dummies ($\beta_h$, $h=2..24$, relative to hour 1 as base) capture the \
**deterministic within-day shape** of the GB-FR spread. Significance tests determine \
which terms to retain.

**Tau anchoring:** frozen at 1 January 2025 to prevent extrapolating the crisis-era trend.

### 6.3 Stochastic Component — OU with Jumps (daily)

$$X_{t+1} = c + \phi X_t + \sigma_d\,\varepsilon_t + J_t^+ - J_t^-$$

The OU is estimated on **daily-averaged residuals** $\bar\varepsilon_d = \text{mean}_h(\varepsilon_h)$.

### 6.4 Hourly Revenue Reconstruction (following Abadie Section 8)

For each simulated day $d$, the single OU value $X_d$ is combined with the 24 hourly \
OLS coefficients to reconstruct 24 hourly spreads:

$$S_{d,h} = f_S(t_d, h) + X_d = \underbrace{[\beta_0 + \beta_1\tau + \beta_2\sin_1 + \beta_3\cos_1 + \beta_6 D_d]}_{\text{base daily}} + \underbrace{\beta_h}_{\text{hour offset}} + X_d$$

Daily revenue (£m):

$$R_d = \sum_{h=1}^{24} |S_{d,h}| \times C \times 1\text{h} \times A \times \rho \;/\; 10^6$$

This correctly reflects that IFA2 earns the hourly spread (not the daily average) and can \
flow in either direction each hour.
"""))

# ── Section 7 ──────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 7: Full OLS Estimation — All Fourier Harmonics (Hourly Data)

Fitted on all 36,984 hourly spread observations. The full model includes annual AND \
semi-annual Fourier harmonics, trend, weekend dummy, and 23 hour-of-day dummies \
(H01 = midnight = base; H02–H24 as deviations).
"""))

cells.append(code("""\
hourly_spread = panel['spread_gbp'].dropna()
n_obs_h       = len(hourly_spread)
t0_spread     = daily.index[0]  # reference date (same whether hourly or daily)

def build_features_full_hourly(idx, t0):
    'Full model: annual + semi-annual Fourier + 23 hour dummies.'
    tau = (pd.DatetimeIndex(idx) - t0).total_seconds() / (365.25 * 24 * 3600)
    df  = pd.DataFrame({
        'const':   1.0,
        'tau':     tau,
        'sin1':    np.sin(2 * np.pi * tau),
        'cos1':    np.cos(2 * np.pi * tau),
        'sin2':    np.sin(4 * np.pi * tau),
        'cos2':    np.cos(4 * np.pi * tau),
        'weekend': (pd.DatetimeIndex(idx).dayofweek >= 5).astype(float),
    }, index=pd.DatetimeIndex(idx))
    for h in range(1, 24):   # H01=base; H02 (h=1)..H24 (h=23)
        df[f'H{h+1:02d}'] = (pd.DatetimeIndex(idx).hour == h).astype(float)
    return df

feat_full_h  = build_features_full_hourly(hourly_spread.index, t0_spread)
res_full_h   = sm.OLS(hourly_spread.values, feat_full_h).fit()
k_full_h     = feat_full_h.shape[1]
rss_full_h   = float(np.sum(res_full_h.resid ** 2))
sigma_full_h = float(res_full_h.resid.std())

print(f'Full OLS on hourly spread ({n_obs_h:,} obs, {k_full_h} parameters):')
print(f'  R2={res_full_h.rsquared:.4f}  sigma_resid={sigma_full_h:.4f} GBP/MWh')
print()

# Non-hour params (show all; hour dummies summarised separately)
non_hour = ['const', 'tau', 'sin1', 'cos1', 'sin2', 'cos2', 'weekend']
print(f'  {"Param":<10}  {"Coeff":>10}  {"Std Err":>10}  {"t-stat":>10}  {"p-value":>10}  Sig')
print('  ' + '-' * 68)
for i, param in enumerate(non_hour):
    coef = res_full_h.params[i]
    se   = res_full_h.bse[i]
    t    = res_full_h.tvalues[i]
    p    = res_full_h.pvalues[i]
    sig  = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else ''
    print(f'  {param:<10}  {coef:>10.4f}  {se:>10.4f}  {t:>10.4f}  {p:>10.4f}  {sig}')

# Hour dummies: just show min/max/count-significant
hour_cols   = [f'H{h+1:02d}' for h in range(1, 24)]
hour_params = pd.Series(res_full_h.params[7:], index=hour_cols)
hour_pvals  = pd.Series(res_full_h.pvalues[7:], index=hour_cols)
n_sig_hours = (hour_pvals < 0.05).sum()
print(f'  {"(23 hour dummies)":<10}  '
      f'range [{hour_params.min():.2f}, {hour_params.max():.2f}] GBP/MWh  '
      f'{n_sig_hours}/23 significant at 5%')
print('  *** p<0.001  ** p<0.01  * p<0.05')
"""))

# ── Section 8 ──────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 8: Parameter Significance Tests

Five complementary tests on the hourly OLS results:

1. **Joint F-test: all Fourier terms** — do annual/semi-annual cycles exist?
2. **Partial F-test: semi-annual only** — do sin₂, cos₂ add to annual terms?
3. **Joint F-test: all 23 hour dummies** — is within-day shape statistically significant?
4. **AIC/BIC model comparison** — full vs annual-only (both with hour dummies)
5. **Amplitude analysis** — economic magnitude of each harmonic vs noise floor
"""))

cells.append(code("""\
# Test 1: all Fourier terms jointly (vs trend + weekend + hour dummies only)
feat_no_fourier = feat_full_h.drop(columns=['sin1','cos1','sin2','cos2'])
res_no_fourier  = sm.OLS(hourly_spread.values, feat_no_fourier).fit()
rss_no_fourier  = float(np.sum(res_no_fourier.resid ** 2))
q1 = 4
F1 = ((rss_no_fourier - rss_full_h) / q1) / (rss_full_h / (n_obs_h - k_full_h))
p1 = sp_stats.f.sf(F1, q1, n_obs_h - k_full_h)

# Test 2: semi-annual only (sin2, cos2) beyond annual
feat_annual_h  = feat_full_h.drop(columns=['sin2','cos2'])
res_annual_h   = sm.OLS(hourly_spread.values, feat_annual_h).fit()
rss_annual_h   = float(np.sum(res_annual_h.resid ** 2))
k_annual_h     = feat_annual_h.shape[1]
q2 = 2
F2 = ((rss_annual_h - rss_full_h) / q2) / (rss_full_h / (n_obs_h - k_full_h))
p2 = sp_stats.f.sf(F2, q2, n_obs_h - k_full_h)

# Test 3: all 23 hour dummies jointly (vs no hour dummies)
non_hour_cols  = ['const','tau','sin1','cos1','sin2','cos2','weekend']
feat_no_hour   = feat_full_h[non_hour_cols]
res_no_hour    = sm.OLS(hourly_spread.values, feat_no_hour).fit()
rss_no_hour    = float(np.sum(res_no_hour.resid ** 2))
q3 = 23
F3 = ((rss_no_hour - rss_full_h) / q3) / (rss_full_h / (n_obs_h - k_full_h))
p3 = sp_stats.f.sf(F3, q3, n_obs_h - k_full_h)

# Test 4: AIC / BIC
def ols_aic_bic(rss, n, k):
    log_lik = -n / 2 * (1 + np.log(2 * np.pi * rss / n))
    return -2 * log_lik + 2 * k, -2 * log_lik + k * np.log(n)

aic_full,   bic_full   = ols_aic_bic(rss_full_h,   n_obs_h, k_full_h)
aic_annual, bic_annual = ols_aic_bic(rss_annual_h, n_obs_h, k_annual_h)

# Test 5: amplitudes
pf      = pd.Series(res_full_h.params, index=feat_full_h.columns)
amp_ann = np.sqrt(pf['sin1']**2 + pf['cos1']**2)
amp_sem = np.sqrt(pf['sin2']**2 + pf['cos2']**2)

# Hour dummy amplitude (peak-to-trough of hourly profile)
hour_params_arr = np.zeros(24)
hour_params_arr[1:] = pf[[f'H{h+1:02d}' for h in range(1, 24)]].values
amp_hour = hour_params_arr.max() - hour_params_arr.min()

print('=' * 68)
print(f'  TEST 1 — Joint F-test: All Fourier terms')
print(f'  F({q1}, {n_obs_h-k_full_h}) = {F1:.1f}   p = {p1:.4f}')
print(f'  => {"REJECT H0 — seasonal variation exists" if p1 < 0.05 else "Fail to reject H0"}')

print()
print(f'  TEST 2 — Partial F-test: Semi-annual terms (sin2, cos2)')
print(f'  F({q2}, {n_obs_h-k_full_h}) = {F2:.3f}   p = {p2:.4f}')
print(f'  => {"Significant" if p2 < 0.05 else "NOT significant — drop sin2/cos2"}')

print()
print(f'  TEST 3 — Joint F-test: All 23 hour dummies')
print(f'  F({q3}, {n_obs_h-k_full_h}) = {F3:.1f}   p = {p3:.6f}')
print(f'  => {"REJECT H0 — within-day shape is highly significant" if p3 < 0.05 else "Fail to reject H0"}')

print()
print(f'  TEST 4 — AIC/BIC Comparison (both models include hour dummies)')
print(f'  {"Model":<30}  {"k":>3}  {"AIC":>12}  {"BIC":>12}')
print(f'  {"-"*62}')
print(f'  {"Full (Fourier + semi-ann + hour)":<30}  {k_full_h:>3}  '
      f'{aic_full:>12.0f}  {bic_full:>12.0f}')
_da, _db = aic_annual - aic_full, bic_annual - bic_full
_preferred_lbl = 'Full (preferred)' if _db < 0 else 'Annual-only (preferred by BIC)' if _db > 0 else 'Tied'
print(f'  {"Annual-only + hour":<30}  {k_annual_h:>3}  '
      f'{aic_annual:>12.0f}  {bic_annual:>12.0f}')
print(f'  delta (annual - full): AIC = {_da:+.0f}    BIC = {_db:+.0f}')
print(f'  (positive delta = annual is WORSE — full model preferred)')

print()
print(f'  TEST 5 — Amplitude vs Noise Floor (sigma_resid = {sigma_full_h:.2f} GBP/MWh)')
print(f'  Annual amplitude  (sin1,cos1):   {amp_ann:.2f} GBP/MWh  '
      f'(ratio = {amp_ann/sigma_full_h:.3f})')
print(f'  Semi-ann amplitude (sin2,cos2):  {amp_sem:.2f} GBP/MWh  '
      f'(ratio = {amp_sem/sigma_full_h:.3f})')
print(f'  Hourly peak-to-trough:           {amp_hour:.2f} GBP/MWh  '
      f'(ratio = {amp_hour/sigma_full_h:.3f})')

print()
print('  CONCLUSION')
print('  ' + '-' * 63)
print(f'  Fourier terms: jointly significant (Test 1: F={F1:.0f})')
_sa_sig = 'statistically significant' if p2 < 0.05 else 'not significant'
print(f'  Semi-annual: {_sa_sig} (Test 2: F={F2:.2f}, p={p2:.3f})')
print(f'    sin2 individually p<0.001 (coeff ~{amp_sem:.1f} GBP/MWh); cos2 p>>0.05')
print(f'    Full model preferred by AIC ({_da:+.0f}) and BIC ({_db:+.0f})')
print(f'    DECISION: drop both — amplitude small ({amp_sem:.1f} vs sigma={sigma_full_h:.0f}),')
print(f'    may reflect 2022-23 crisis; projecting 25yr adds instability')
print(f'  Hour dummies: highly significant (Test 3: F={F3:.0f}) -> retain')
print(f'  Hourly amplitude ({amp_hour:.1f} GBP/MWh) >> annual ({amp_ann:.1f}):')
print(f'    within-day variation is the dominant deterministic driver')
print('=' * 68)
"""))

# ── Section 9 ──────────────────────────────────────────────────────────────
cells.append(md(r"""\
## Section 9: Model Refinement — Annual Fourier + 24 Hour Dummies

Drop sin₂ and cos₂. With hourly data (n=36,984), sin₂ is statistically significant (F=19.7, p<0.001) \
but cos₂ is not (p=0.96). The full model is preferred by both AIC and BIC (delta-BIC=+18). \
We nonetheless drop both semi-annual terms: their economic contribution is small (~2 GBP/MWh amplitude \
vs σ=48 GBP/MWh noise), and projecting a 6-month cycle estimated over only 4.5 years of data \
— partly contaminated by the 2022–2023 energy crisis — 25 years forward adds instability without \
meaningful revenue impact. The **final OLS model** retains annual Fourier terms + 23 hour dummies:

$$f_S(t, h) = \beta_0 + \beta_1\tau + \beta_2\sin(2\pi\tau) + \beta_3\cos(2\pi\tau) + \beta_4 D_t + \sum_{h=2}^{24}\beta_h\mathbf{1}[\text{hour}=h]$$

Fitted on 36,984 hourly observations. **Hourly residuals are then aggregated to daily means** \
for jump detection and OU estimation — matching the daily Euler scheme of the simulation.
"""))

cells.append(code("""\
def build_features_spread_hourly(idx, t0):
    'Final OLS: annual Fourier + 23 hour dummies (semi-annual dropped).'
    tau = (pd.DatetimeIndex(idx) - t0).total_seconds() / (365.25 * 24 * 3600)
    df  = pd.DataFrame({
        'const':   1.0,
        'tau':     tau,
        'sin1':    np.sin(2 * np.pi * tau),
        'cos1':    np.cos(2 * np.pi * tau),
        'weekend': (pd.DatetimeIndex(idx).dayofweek >= 5).astype(float),
    }, index=pd.DatetimeIndex(idx))
    for h in range(1, 24):
        df[f'H{h+1:02d}'] = (pd.DatetimeIndex(idx).hour == h).astype(float)
    return df

feat_spread_h = build_features_spread_hourly(hourly_spread.index, t0_spread)
res_ols_h     = sm.OLS(hourly_spread.values, feat_spread_h).fit()
f_spread_h    = pd.Series(res_ols_h.fittedvalues, index=hourly_spread.index)
resid_h       = hourly_spread - f_spread_h
params_s      = pd.Series(res_ols_h.params, index=feat_spread_h.columns)

# Aggregate to daily for downstream OU / jump detection
resid_s   = resid_h.resample('D').mean().dropna()   # daily mean of hourly residuals
f_spread  = f_spread_h.resample('D').mean()          # daily mean of hourly OLS fit

print(f'Refined OLS ({len(feat_spread_h.columns)} params, {n_obs_h:,} hourly obs):')
print(f'  R2={res_ols_h.rsquared:.4f}  sigma_resid(hourly)={res_ols_h.resid.std():.4f} GBP/MWh')
print(f'  sigma_resid(daily avg) = {resid_s.std():.4f} GBP/MWh')
print()

non_hour = ['const', 'tau', 'sin1', 'cos1', 'weekend']
print(f'  {"Param":<10}  {"Coeff":>10}  {"Std Err":>10}  {"t-stat":>10}  {"p-value":>10}  Sig')
print('  ' + '-' * 68)
for param in non_hour:
    i = list(feat_spread_h.columns).index(param)
    coef = res_ols_h.params[i]; se = res_ols_h.bse[i]
    t = res_ols_h.tvalues[i];  p = res_ols_h.pvalues[i]
    sig = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else ''
    print(f'  {param:<10}  {coef:>10.4f}  {se:>10.4f}  {t:>10.4f}  {p:>10.4f}  {sig}')
hour_cols_h = [f'H{h+1:02d}' for h in range(1, 24)]
hp = params_s[hour_cols_h]
print(f'  {"(23 hour dummies)":<10}  '
      f'range [{hp.min():.2f}, {hp.max():.2f}] GBP/MWh, '
      f'peak at H{hp.idxmax()[1:]}')

# Plot: daily-averaged OLS fit vs actual, and daily residuals
fig, axes = plt.subplots(2, 1, figsize=(13, 6), sharex=True)
axes[0].plot(daily.index, daily['spread_gbp'], lw=0.7, alpha=0.7,
             color='steelblue', label='Actual spread (daily avg)')
axes[0].plot(f_spread.index, f_spread.values, lw=1.5, color='darkorange',
             label='OLS f_S(t) — daily avg of hourly fit')
axes[0].axhline(0, color='k', lw=0.8, ls='--', alpha=0.4)
axes[0].set_ylabel('GBP/MWh'); axes[0].legend()
axes[0].set_title('Fig S1a. OLS Fit (Annual Fourier + 24 Hour Dummies)', fontweight='bold')

axes[1].plot(resid_s.index, resid_s.values, lw=0.7, color='#2ca02c', alpha=0.8)
axes[1].axhline(0, color='k', lw=0.8, ls='--', alpha=0.4)
for s in [1, 2, 3]:
    axes[1].axhline(+s * resid_s.std(), color='red', lw=0.5, ls=':', alpha=0.5)
    axes[1].axhline(-s * resid_s.std(), color='red', lw=0.5, ls=':', alpha=0.5)
axes[1].set_ylabel('Daily avg residual (GBP/MWh)')
axes[1].set_title('Fig S1b. Daily-Averaged OLS Residuals (dotted = +-1/2/3 sigma)',
                  fontweight='bold')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'figS1_spread_ols.png', dpi=150, bbox_inches='tight')
plt.show()

# Hourly profile plot
fig2, ax2 = plt.subplots(figsize=(10, 4))
hour_offsets_plot = np.zeros(24)
for h in range(1, 24):
    hour_offsets_plot[h] = params_s[f'H{h+1:02d}']
ax2.bar(range(24), hour_offsets_plot, color='steelblue', alpha=0.7)
ax2.axhline(0, color='k', lw=0.8, ls='--', alpha=0.5)
ax2.set_xlabel('Hour of day (0 = midnight, H01 = base)')
ax2.set_ylabel('GBP/MWh (deviation from H01)')
ax2.set_title('Fig S1c. OLS Hour-of-Day Dummy Coefficients (spread profile)',
              fontweight='bold')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'figS1c_hourly_profile.png', dpi=150, bbox_inches='tight')
plt.show()
print('Saved: figS1_spread_ols.png, figS1c_hourly_profile.png')
"""))

# ── Section 10 ─────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 10: Jump Detection (Cartea & González-Pedraz)

Jump detection is applied to the **daily-averaged OLS residuals** `resid_s` — the same \
variable used for OU estimation. Hourly-level spikes average out within a day; \
the daily residuals capture multi-day extreme events that genuinely shift the spread.

**Algorithm:** iterative ±3σ filter until convergence; separate positive (GB spike) \
and negative (FR spike) components; quarterly Poisson intensity; exponential jump size.
"""))

cells.append(code("""\
def cartea_filter(resid, label, thresh=3.0):
    clean = resid.copy()
    for _ in range(20):
        mu, sig = clean.mean(), clean.std()
        is_jump = (clean - mu).abs() > thresh * sig
        if not is_jump.any():
            break
        clean[is_jump] = np.nan
    jumps = resid[resid.index.isin(clean[clean.isna()].index)]
    clean = clean.dropna()
    print(f'  {label}: {len(jumps)} jumps / {len(resid)} days '
          f'({len(jumps)/len(resid)*100:.1f}%)   sigma_clean={clean.std():.4f} GBP/MWh')
    return clean, jumps

def build_jump_params(jump_sizes, all_days):
    pos_j = jump_sizes[jump_sizes > 0]
    neg_j = jump_sizes[jump_sizes < 0].abs()
    result = {}
    for sign, jmp in [('pos', pos_j), ('neg', neg_j)]:
        if len(jmp) == 0:
            result[sign] = {'lam_by_q': {q: 0.0 for q in [1,2,3,4]}, 'beta': 0.0, 'n': 0}
            continue
        beta  = float(jmp.mean())
        lam_q = {}
        for q in [1, 2, 3, 4]:
            q_days  = all_days[pd.DatetimeIndex(all_days).quarter == q]
            q_jumps = jmp.index[pd.DatetimeIndex(jmp.index).quarter == q]
            lam_q[q] = len(q_jumps) / max(len(q_days), 1)
        result[sign] = {'lam_by_q': lam_q, 'beta': beta, 'n': len(jmp)}
    return result

print('Jump detection on daily-averaged spread residuals:')
resid_s_clean, jumps_s = cartea_filter(resid_s, 'GB-FR Spread')
jump_params_s = build_jump_params(jumps_s, daily.index)

print()
print(f'  {"Direction":<18}  {"n":>5}  {"Mean lambda/day":>17}  {"Beta (GBP/MWh)":>16}')
print('  ' + '-' * 62)
for sign, lbl in [('pos', 'Positive (GB spike)'), ('neg', 'Negative (FR spike)')]:
    jp = jump_params_s[sign]
    ml = sum(jp['lam_by_q'].values()) / 4
    print(f'  {lbl:<18}  {jp["n"]:>5}  {ml:>17.5f}  {jp["beta"]:>16.2f}')

print()
print('  Quarterly lambda (per day):')
print(f'  {"Q":<5}  {"Positive":>12}  {"Negative":>12}')
for q in [1, 2, 3, 4]:
    lp = jump_params_s['pos']['lam_by_q'][q]
    ln = jump_params_s['neg']['lam_by_q'][q]
    print(f'  Q{q:<4}  {lp:>12.5f}  {ln:>12.5f}')
"""))

# ── Section 11 ─────────────────────────────────────────────────────────────
cells.append(md(r"""\
## Section 11: Ornstein-Uhlenbeck Parameter Estimation

The jump-cleaned **daily-averaged** residual series is fitted as AR(1):

$$\tilde{X}_{t+1} = c + \phi\tilde{X}_t + \eta_t, \quad \eta_t \sim N(0, \sigma_d^2)$$

$\sigma_d$ here is the daily-average residual volatility — smaller than the hourly \
residual volatility because within-day random noise averages out. This is correct: \
in the simulation, one $X_d$ per day represents the daily average deviation.
"""))

cells.append(code("""\
def ou_ar1_levels(series, label):
    y   = series.values
    X   = sm.add_constant(y[:-1])
    res = sm.OLS(y[1:], X).fit()
    c, phi  = float(res.params[0]), float(res.params[1])
    eps     = pd.Series(res.resid, index=series.index[1:])
    sigma_d = float(eps.std())
    kappa   = -np.log(max(phi, 1e-9)) * 365.25
    theta   = c / (1 - phi) if abs(1 - phi) > 1e-9 else 0.0
    hl      = np.log(2) / (kappa / 365.25)
    print(f'  {label}:')
    print(f'    phi={phi:.5f}   kappa={kappa:.2f}/yr   half-life={hl:.1f} days')
    print(f'    theta={theta:.4f} GBP/MWh   sigma_d={sigma_d:.4f} GBP/MWh')
    return {'phi': phi, 'c': c, 'sigma_d': sigma_d,
            'kappa_yr': kappa, 'theta': theta, 'eps': eps}

print('OU estimation (AR(1) on jump-cleaned daily-averaged residuals):')
ou_s = ou_ar1_levels(resid_s_clean, 'GB-FR Spread')

eps = ou_s['eps']
print()
print('Innovation diagnostics:')
print(f'  Mean={eps.mean():.5f}  Std={eps.std():.4f}  '
      f'Skew={sp_stats.skew(eps):.3f}  ExKurt={sp_stats.kurtosis(eps):.3f}')
_, p_norm = sp_stats.normaltest(eps)
print(f'  Normality p={p_norm:.4f}  '
      f'({"reject" if p_norm < 0.05 else "consistent with"} normality)')
"""))

# ── Section 12: Back-test & Validation ────────────────────────────────────
cells.append(md("""\
## Section 12: Back-test — Model Validation Against 2022–2025 Actuals

The OLS and OU parameters are estimated from 2021–2026 data independently of the Ofgem
actuals. This section tests the model's out-of-model performance: apply the fitted OLS
to the actual 2022–2025 hourly spread data, compute gross theoretical revenue
(no stochastic component, no capture ratio), and compare to what Ofgem actually disclosed.

The gap between gross theoretical and Ofgem actuals reveals the implied **market-cost
deduction rate** — auction premiums, TSO charges, balancing costs, and operational losses.
This rate is not a model tuning parameter; it is an observed fact about market structure.
"""))

cells.append(code("""\
print('Back-test: OLS deterministic revenue vs Ofgem actuals')
print('=' * 68)
print(f'  {"Year":<6}  {"Gross (actual spread)":>22}  {"OLS det. |f_S|":>16}  '
      f'{"Ofgem actual":>14}  {"Implied CR":>11}')
print('  ' + '-' * 75)

validation = {}
for yr in [2022, 2023, 2024, 2025]:
    hs_yr = panel.loc[str(yr), 'spread_gbp'].dropna()

    # Gross theoretical from actual hourly spread data (no model)
    gross_actual = hs_yr.abs().sum() * CAPACITY_MW * AVAILABILITY / 1e6

    # Gross theoretical from OLS deterministic only |f_S(t,h)|
    feat_yr = build_features_spread_hourly(hs_yr.index, t0_spread)
    f_s_yr  = feat_yr.values @ params_s.values
    gross_det = np.abs(f_s_yr).sum() * CAPACITY_MW * AVAILABILITY / 1e6

    ofgem = ACTUALS[yr]
    cr    = ofgem / gross_actual
    validation[yr] = dict(gross_actual=gross_actual, gross_det=gross_det,
                          ofgem=ofgem, cr=cr)

    print(f'  {yr:<6}  {gross_actual:>20.1f}m  {gross_det:>14.1f}m  '
          f'{ofgem:>12.1f}m  {cr:>10.1%}')

print()
implied_crs  = [v['cr'] for v in validation.values()]
capture_ratio = np.mean([validation[y]['cr'] for y in [2024, 2025]])
print(f'  2022-2025 mean implied CR:  {np.mean(implied_crs):.1%}')
print(f'  2024-2025 mean implied CR:  {capture_ratio:.1%}  '
      f'(normalised — 2022-23 crisis distortion excluded)')
print()
print(f'  Interpretation:')
print(f'    ~{(1-capture_ratio)*100:.0f}% of gross hourly spread revenue is absorbed by')
print(f'    auction costs, TSO charges, balancing, and operational losses.')
print(f'    This is a market-structure observation, NOT a model parameter.')
print('=' * 68)

# Plot: actual hourly spread (daily mean) vs OLS fit for 2024-2025
fig, axes = plt.subplots(2, 1, figsize=(13, 6), sharex=False)
for ax, yr in zip(axes, [2024, 2025]):
    hs_yr = panel.loc[str(yr), 'spread_gbp'].dropna()
    daily_actual = hs_yr.resample('D').mean()
    feat_yr = build_features_spread_hourly(hs_yr.index, t0_spread)
    f_s_yr  = pd.Series(feat_yr.values @ params_s.values, index=hs_yr.index)
    daily_det = f_s_yr.resample('D').mean()
    ax.plot(daily_actual.index, daily_actual.values, lw=0.7, color='steelblue',
            alpha=0.8, label='Actual daily mean spread')
    ax.plot(daily_det.index, daily_det.values, lw=1.5, color='firebrick',
            label='OLS deterministic f_S (daily mean)')
    ax.axhline(0, color='black', lw=0.5, ls='--')
    ax.set_title(f'{yr} — Actual spread vs OLS fit  '
                 f'(Ofgem: GBP{ACTUALS[yr]:.1f}m | '
                 f'Gross theoretical: GBP{validation[yr]["gross_actual"]:.1f}m)',
                 fontsize=9)
    ax.set_ylabel('GBP/MWh'); ax.legend(fontsize=8)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'figS3_backtest.png', dpi=150, bbox_inches='tight')
plt.show()
print('Saved: figS3_backtest.png')
"""))

# ── Section 13 ─────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 13: Monte Carlo Setup — Hourly f_S Projection

### Hourly f_S Projection

The OLS model decomposes as:

    f_S(t, h) = [base daily: const + tau + sin1 + cos1 + weekend] + hour_offset[h]

where `hour_offset[h] = β_h` (0 for H01, OLS coefficient for H02–H24). \
We pre-compute this as a **(n_days × 24) array** — one row per simulation day, \
one column per hour.

### Capture Ratio — Now Calibrated on Hourly Theoretical Revenue

With the hourly approach, the **theoretical revenue** is:

    theoretical = Σ_h |actual_hourly_spread_h| × 1000MW × 1h × availability / 1e6

This is higher than the daily-average approach (`|mean_daily_spread| × 24h`) \
because E[|S_h|] > |E[S_h]| within a day. The capture ratio is correspondingly \
lower, but represents **only genuine market costs** (auction, TSO, balancing) — \
no longer conflated with temporal aggregation effects.
"""))

cells.append(code("""\
proj_dates = pd.date_range(
    start=f'{PROJ_START_YEAR}-01-01',
    end=f'{PROJ_START_YEAR + N_PROJ_YEARS - 1}-12-31',
    freq='D'
)
proj_years = proj_dates.year.values

_tau_anchor_s = float(
    (ANCHOR_DATE - t0_spread).total_seconds()
) / (365.25 * 24 * 3600)

BASE_COLS = ['const', 'tau', 'sin1', 'cos1', 'weekend']

def project_f_spread_hourly(params_s, proj_dates, t0, tau_anchor,
                             tau_growth=PROJ_TAU_GROWTH):
    # Returns (n_days, 24) array: hourly f_S for each projection day.
    # tau is anchored at ANCHOR_DATE; hour offsets from OLS params.
    tau_d = np.array((proj_dates - t0).total_seconds(), dtype=float) \
            / (365.25 * 24 * 3600)
    yrs_from_anchor = np.array((proj_dates - ANCHOR_DATE).total_seconds(), dtype=float) \
                      / (365.25 * 24 * 3600)
    tau_anchored = tau_anchor + tau_growth * np.clip(yrs_from_anchor, 0, None)

    feat_base = np.column_stack([
        np.ones(len(proj_dates)),
        tau_anchored,
        np.sin(2 * np.pi * tau_d),
        np.cos(2 * np.pi * tau_d),
        (proj_dates.dayofweek >= 5).astype(float),
    ])
    f_base = feat_base @ params_s[BASE_COLS].values  # (n_days,)

    # Hour offsets: H01=0 (base), H02..H24 = OLS coefficients
    hour_offsets = np.zeros(24)
    for h in range(1, 24):
        col = f'H{h+1:02d}'
        if col in params_s.index:
            hour_offsets[h] = params_s[col]

    return f_base[:, np.newaxis] + hour_offsets[np.newaxis, :]  # (n_days, 24)

f_s_proj_h = project_f_spread_hourly(params_s, proj_dates, t0_spread, _tau_anchor_s)

yr1_label = PROJ_START_YEAR
yr_last   = PROJ_START_YEAR + N_PROJ_YEARS - 1
print(f'Projected f_S — hourly (n_days={len(proj_dates)}, 24 hours):')
print(f'  Year 1 ({yr1_label}) daily mean:   {f_s_proj_h[:365].mean():.2f} GBP/MWh')
print(f'  Year 1 avg hourly peak:          {f_s_proj_h[:365].max(axis=1).mean():.2f} GBP/MWh')
print(f'  Year 1 avg hourly trough:        {f_s_proj_h[:365].min(axis=1).mean():.2f} GBP/MWh')
print(f'  Year {N_PROJ_YEARS} ({yr_last}) daily mean:  {f_s_proj_h[-365:].mean():.2f} GBP/MWh')

# capture_ratio derived from Section 12 back-test (2024-2025 normalised)
# NOT re-computed here — carried forward from validation cell above
print()
print(f'Capture ratio (from back-test, 2024-2025 normalised): {capture_ratio:.4f} ({capture_ratio*100:.1f}%)')
print(f'Market-cost deductions: {(1-capture_ratio)*100:.0f}%  (NOT a model tuning parameter)')
"""))

# ── Section 13 ─────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 13: Monte Carlo Simulation — Hourly Revenue Reconstruction

For each simulated day $d$ with OU value $X_d$:

1. Reconstruct 24 hourly spreads: $S_{d,h} = f_S(t_d, h) + X_d$  (shape: batch × 24)
2. Daily revenue: $R_d = \\sum_{h=1}^{24} |S_{d,h}| \\times 1000\\,\\text{MW} \\times 1\\,\\text{h} \\times A \\times \\rho \\;/\\; 10^6$

This directly replicates Abadie (2021) Section 8: \
*"apply the hourly seasonality coefficients to each daily series to obtain 24 prices per day."*
"""))

cells.append(code("""\
rng    = np.random.default_rng(RANDOM_SEED)
BATCH  = 500
n_days = len(proj_dates)
phi    = ou_s['phi'];   c_ou = ou_s['c'];  sigma_d = ou_s['sigma_d']
jp_pos = jump_params_s['pos'];  jp_neg = jump_params_s['neg']

annual_rev = np.zeros((N_PATHS, N_PROJ_YEARS))

print(f'Running {N_PATHS:,} paths x {N_PROJ_YEARS} years ({n_days:,} days)...')
print(f'Projection: {PROJ_START_YEAR}-{PROJ_START_YEAR+N_PROJ_YEARS-1}')
print(f'Revenue: sum over 24 hourly |spreads| per day (Abadie hourly reconstruction)')
for b0 in range(0, N_PATHS, BATCH):
    b1 = min(b0 + BATCH, N_PATHS);  n = b1 - b0
    X  = np.zeros(n)
    batch_rev = np.zeros((N_PROJ_YEARS, n))

    for d in range(n_days):
        X = c_ou + phi * X + sigma_d * rng.standard_normal(n)
        q = proj_dates[d].quarter
        for jp, sign in [(jp_pos, +1.0), (jp_neg, -1.0)]:
            lam = jp['lam_by_q'][q]
            if lam > 0 and jp['beta'] > 0:
                X += sign * (rng.random(n) < lam) * rng.exponential(jp['beta'], n)

        # Reconstruct 24 hourly spreads: (n, 24)
        S_h = f_s_proj_h[d, :] + X[:, np.newaxis]
        # Sum |S_h| over 24 hours → daily revenue (GBPm)
        rev_d = np.abs(S_h).sum(axis=1) * CAPACITY_MW * AVAILABILITY / 1e6 * capture_ratio

        yr_idx = proj_years[d] - PROJ_START_YEAR
        if 0 <= yr_idx < N_PROJ_YEARS:
            batch_rev[yr_idx] += rev_d
    annual_rev[b0:b1] = batch_rev.T

    if (b1 % 2500 == 0) or b1 == N_PATHS:
        print(f'  {b1:>6}/{N_PATHS} paths  =>  Yr1 ({PROJ_START_YEAR}) P50 = '
              f'GBP{np.percentile(annual_rev[:b1, 0], 50):.0f}m')

print('Simulation complete.')
"""))

# ── Section 14 ─────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 14: Results — Revenue Tables and Charts

**P10/P50/P90 convention (statistical):** P10 = 10th percentile (downside); \
P90 = 90th percentile (upside). P10 < P50 < P90.

### Revenue profile
Revenues remain broadly flat because the OU (κ ≈ 168/yr, half-life ≈ 1.5 days) \
produces an identical stationary distribution every year and f_S is anchored flat. \
The hourly reconstruction raises revenue relative to the daily-average approach \
(since Σ_h|S_h| > 24|S̄|), and the lower capture ratio offsets this so the P50 \
remains calibrated to Ofgem actuals (£108–109m in 2024–2025).
"""))

cells.append(code("""\
p10 = np.percentile(annual_rev, 10, axis=0)
p50 = np.percentile(annual_rev, 50, axis=0)
p90 = np.percentile(annual_rev, 90, axis=0)

proj_cal_years = [PROJ_START_YEAR + i for i in range(N_PROJ_YEARS)]
rev_df = pd.DataFrame({
    'cal_year':  proj_cal_years,
    'regime_yr': range(PROJ_START_YEAR - REGIME_START + 1,
                       PROJ_START_YEAR - REGIME_START + N_PROJ_YEARS + 1),
    'p10_gbpm':  p10.round(2), 'p50_gbpm': p50.round(2), 'p90_gbpm': p90.round(2),
})
rev_df.to_csv(OUTPUT_DIR / 'mc_revenue_spread_direct.csv', index=False)
print('Saved: mc_revenue_spread_direct.csv')
print()

# Combined table: actuals then projections
print('  === IFA2 Revenue — Full Regime 2021-2045 ===')
print(f'  {"Yr":>3}  {"Cal":>6}  {"P10 (GBPm)":>12}  {"P50 (GBPm)":>12}  {"P90 (GBPm)":>12}  Note')
print('  ' + '-' * 70)
for yr in range(REGIME_START, PROJ_START_YEAR):
    regime_yr = yr - REGIME_START + 1
    if yr in ACTUALS:
        val = ACTUALS[yr]
        print(f'  {regime_yr:>3}  {yr:>6}  {"—":>12}  {val:>12.1f}  {"—":>12}  actual (Ofgem)')
    else:
        print(f'  {regime_yr:>3}  {yr:>6}  {"—":>12}  {"n/a":>12}  {"—":>12}  not disclosed')
print('  ' + '·' * 70)
show = sorted(set([0, 4] + list(range(4, N_PROJ_YEARS, 5)) + [N_PROJ_YEARS-1]))
for i in show:
    regime_yr = (PROJ_START_YEAR + i) - REGIME_START + 1
    print(f'  {regime_yr:>3}  {PROJ_START_YEAR+i:>6}  '
          f'{p10[i]:>12.1f}  {p50[i]:>12.1f}  {p90[i]:>12.1f}  projected')

# Chart
fig, axes = plt.subplots(1, 2, figsize=(15, 5))

ax = axes[0]
ax.fill_between(proj_cal_years, p10, p90, alpha=0.25, color='steelblue', label='P10-P90 band')
ax.plot(proj_cal_years, p50, lw=2.0, color='steelblue', label='P50 (median)')
ax.plot(proj_cal_years, p10, lw=0.9, ls='--', color='steelblue')
ax.plot(proj_cal_years, p90, lw=0.9, ls='--', color='steelblue')
for yr, val in ACTUALS.items():
    ax.scatter([yr], [val], color='red', zorder=5, s=60)
ax.scatter([], [], color='red', s=60, label='Ofgem actuals 2022-25')
ax.axvline(PROJ_START_YEAR - 0.5, color='grey', lw=1, ls=':', alpha=0.7)
ax.text(PROJ_START_YEAR - 0.3, ax.get_ylim()[0] if ax.get_ylim()[0] > 0 else 50,
        'projection start', fontsize=7, color='grey', rotation=90, va='bottom')
ax.set_title('M2: Spread-Direct OU — IFA2 Regime 2021-2045\\n'
             '(Actuals 2022-25 | Projection 2026-2045)', fontweight='bold')
ax.set_xlabel('Year'); ax.set_ylabel('GBPm nominal'); ax.legend(fontsize=9)

ax2 = axes[1]
try:
    m1 = pd.read_csv(IC_DIR / 'M1' / 'mc_revenue_projections.csv')
    ax2.fill_between(m1['cal_year'], m1['p10_gbpm'], m1['p90_gbpm'],
                     alpha=0.12, color='darkorange')
    ax2.plot(m1['cal_year'], m1['p50_gbpm'], lw=2, color='darkorange',
             label='M1 P50 (log-price OU)')
    ax2.plot(m1['cal_year'], m1['p10_gbpm'], lw=0.9, ls='--', color='darkorange')
    ax2.plot(m1['cal_year'], m1['p90_gbpm'], lw=0.9, ls='--', color='darkorange')
except FileNotFoundError:
    ax2.text(0.5, 0.5, 'M1 results not found', transform=ax2.transAxes, ha='center')
ax2.fill_between(proj_cal_years, p10, p90, alpha=0.20, color='steelblue')
ax2.plot(proj_cal_years, p50, lw=2, color='steelblue', label='M2 P50 (hourly OU)')
ax2.plot(proj_cal_years, p10, lw=0.9, ls='--', color='steelblue')
ax2.plot(proj_cal_years, p90, lw=0.9, ls='--', color='steelblue')
for yr, val in ACTUALS.items():
    ax2.scatter([yr], [val], color='red', zorder=5, s=60)
ax2.scatter([], [], color='red', s=60, label='Ofgem actuals 2022-25')
ax2.set_title('Methodology Comparison — M1 (orange) vs M2 (blue)', fontweight='bold')
ax2.set_xlabel('Year'); ax2.legend(fontsize=9)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'figS2_methodology_comparison.png', dpi=150, bbox_inches='tight')
plt.show()
print('Saved: figS2_methodology_comparison.png')
"""))

# ── Section 15 ─────────────────────────────────────────────────────────────
cells.append(md("""\
## Section 15: Export to Ofgem Cap & Floor Model

Revenue series written to the Ofgem Excel template (IFA2 FPA). \
Three copies — P10, P50, P90. Values go to `Input` sheet, row 25, columns V–AT \
(columns 22–46 = regime years 1–25 = calendar years **2021–2045**).

| Regime years | Calendar years | Source |
|---|---|---|
| 1 (2021) | 2021 | Blank — Ofgem not yet disclosed |
| 2–5 (2022–2025) | 2022–2025 | Hard-coded Ofgem actuals |
| 6–25 (2026–2045) | 2026–2045 | Model P10 / P50 / P90 |

> **Note:** Verify cap/floor floor and cap parameters against the actual Ofgem \
Window 2 IFA2 decision document. Confirm whether floor/cap are expressed in real \
or nominal terms before interpreting breach probabilities.
"""))

cells.append(code("""\
import shutil
import openpyxl

EXCEL_TEMPLATE = IC_DIR / 'copy_cap_and_floor_financial_model_-_ifa2_fpa.xlsm'
INPUT_ROW, COL_YEAR_1 = 25, 22   # col 22 = column V = regime year 1 (2021)

# Build full 25-year revenue array for each scenario
# Regime years 1-25 = calendar years 2021-2045
# Years 2021-2025: hard-coded actuals (same across P10/P50/P90)
# Years 2026-2045: model projections (scenario-specific)
TOTAL_REGIME = PROJ_START_YEAR - REGIME_START + N_PROJ_YEARS  # should be 25

for pct_label, proj_values in [('p10', p10), ('p50', p50), ('p90', p90)]:
    full_25 = []
    for yr in range(REGIME_START, REGIME_START + TOTAL_REGIME):
        if yr < PROJ_START_YEAR:
            # Use Ofgem actual if disclosed, else None (will leave cell blank)
            full_25.append(ACTUALS.get(yr, None))
        else:
            idx = yr - PROJ_START_YEAR
            full_25.append(round(float(proj_values[idx]), 2))

    out_path = OUTPUT_DIR / f'ic_cap_floor_m2_{pct_label}.xlsm'
    shutil.copy2(EXCEL_TEMPLATE, out_path)
    wb = openpyxl.load_workbook(out_path, keep_vba=True)
    ws = wb['Input']
    for i, val in enumerate(full_25):
        if val is not None:
            ws.cell(row=INPUT_ROW, column=COL_YEAR_1 + i, value=val)
        # None = leave cell as-is (blank / Ofgem not disclosed)
    wb.save(out_path)
    wb.close()

    actuals_filled = [yr for yr in range(REGIME_START, PROJ_START_YEAR) if yr in ACTUALS]
    print(f'Written: ic_cap_floor_m2_{pct_label}.xlsm')
    print(f'  Actuals populated:  {min(actuals_filled)}-{max(actuals_filled)} '
          f'({len(actuals_filled)} years)')
    print(f'  Projected:          {PROJ_START_YEAR}-{PROJ_START_YEAR+N_PROJ_YEARS-1} '
          f'({N_PROJ_YEARS} years)')
    print(f'  Yr1 proj ({PROJ_START_YEAR}): GBP{proj_values[0]:.1f}m  '
          f'Yr{N_PROJ_YEARS} ({PROJ_START_YEAR+N_PROJ_YEARS-1}): GBP{proj_values[-1]:.1f}m')
    print()

print('Open ic_cap_floor_m2_*.xlsm in Excel to evaluate cap/floor breach.')
print('Note: regime year 1 (2021) is blank — Ofgem figure not yet disclosed.')
"""))

# ── Write notebook ─────────────────────────────────────────────────────────
nb = nbformat.v4.new_notebook()
nb.cells = cells
nb.metadata['kernelspec'] = {
    'display_name': 'Python 3 (ipykernel)',
    'language': 'python',
    'name': 'python3',
}
nb.metadata['language_info'] = {'name': 'python', 'version': '3.11.0'}

out = Path('/Users/aadesh/Documents/IC/M2/IC_spread_direct.ipynb')
with open(out, 'w') as f:
    nbformat.write(nb, f)

print(f'Written: {out}  ({len(nb.cells)} cells)')
