"""
ACF diagnostic on X_t (OU residual) from the IFA2 spread model.

Replicates the IC_spread_direct_v2.ipynb pipeline (data load, RPI deflation,
OLS, Cartea jump filter, NLS OU+jump) then runs:
  1. Full sample vs post-crisis (Jan 2023+) comparison
  2. ACF table at selected lags: empirical vs AR(1) phi^k vs 95% CI
  3. Ljung-Box on X_t levels  (lags 5, 10, 20, 30)
  4. Ljung-Box on X_t^2       (lags 5, 10, 20, 30) — volatility clustering
  5. 2×2 plot saved as acf_xt_check.png

Decision:
  Levels LB p > 0.05 AND empirical ACF ≈ phi^k  → AR(1) fine, no HMM needed
  Levels LB p < 0.05 OR ACF elevated at lags 10-30 → under-specified memory
  Squared LB p < 0.05                             → volatility clustering present
"""

from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.tsa.stattools import acf
from statsmodels.stats.diagnostic import acorr_ljungbox
from scipy.optimize import minimize_scalar

warnings.filterwarnings('ignore')

# ── Paths / constants ─────────────────────────────────────────────────────
IC_DIR     = Path('/Users/aadesh/Documents/IC')
EXCEL_PATH = IC_DIR / 'GB-FR07.xlsx'
HOL_PATH   = Path('/Users/aadesh/Downloads/Fixed_Public_Holidays_GB_France.xlsx')
OUT_PATH   = IC_DIR / 'M2' / 'acf_xt_check.png'

_HIST_RPI = {2021: 310.794, 2022: 320.864, 2023: 331.260,
             2024: 341.993, 2025: 353.073, 2026: 364.513}
_RPI_1617 = 264.992
SHORT_GAP_H = 4

# ── 1. Data loading ────────────────────────────────────────────────────────
print('Loading data...')
xl      = pd.ExcelFile(EXCEL_PATH)
gb_wide = xl.parse('GB_FINAL')
fr_wide = xl.parse('FR_FINAL')
fx_raw  = xl.parse('GBP-EUR')

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

gb_s = _wide_to_hourly(gb_wide, 'gb_price_gbp')
fr_s = _wide_to_hourly(fr_wide, 'fr_price_eur')
fx   = fx_raw.copy()
fx.columns = ['date', 'fx_eur_gbp']
fx['date'] = pd.to_datetime(fx['date'])
fx = fx.dropna(subset=['fx_eur_gbp']).set_index('date').sort_index()
fx = fx.reindex(pd.date_range(fx.index.min(), fx.index.max(), freq='D')).ffill()

# ── 2. Panel construction + RPI deflation ─────────────────────────────────
panel = pd.concat([gb_s, fr_s], axis=1).sort_index()
panel = panel[~panel.index.duplicated(keep='last')]
start = max(panel['gb_price_gbp'].first_valid_index(), panel['fr_price_eur'].first_valid_index())
end   = min(panel['gb_price_gbp'].last_valid_index(),  panel['fr_price_eur'].last_valid_index())
panel = panel.loc[start:end]
panel = panel.reindex(pd.date_range(panel.index.min(), panel.index.max(), freq='h'))
panel = panel.interpolate(method='linear', limit=SHORT_GAP_H).dropna()
panel['fx_eur_gbp']   = pd.Series(panel.index.normalize().map(fx['fx_eur_gbp']),
                                   index=panel.index).bfill().ffill()
panel['fr_price_gbp'] = panel['fr_price_eur'] * panel['fx_eur_gbp']
panel['spread_gbp']   = panel['gb_price_gbp'] - panel['fr_price_gbp']
panel = panel.dropna(subset=['gb_price_gbp', 'fr_price_gbp', 'spread_gbp'])

_rpi_defl = pd.Series(
    [_RPI_1617 / _HIST_RPI.get(d.year, _HIST_RPI[max(_HIST_RPI)]) for d in panel.index],
    index=panel.index)
panel['gb_price_gbp'] *= _rpi_defl
panel['fr_price_gbp'] *= _rpi_defl
panel['spread_gbp']   *= _rpi_defl

t0    = panel.index.normalize()[0]
print(f'  Panel: {panel.index.min().date()} → {panel.index.max().date()}'
      f'  ({len(panel):,} hourly obs)')

# ── 3. Holidays ───────────────────────────────────────────────────────────
_hol_df = pd.read_excel(HOL_PATH, sheet_name='Fixed Public Holidays')
def _make_holidays(years, df, col):
    dates = set()
    for _, row in df[df[col] == 'Yes'].iterrows():
        for yr in years:
            try:
                dates.add(pd.Timestamp(yr, int(row['Month']), int(row['Day'])))
            except ValueError:
                pass
    return dates
_yrs = range(panel.index.year.min(), panel.index.year.max() + 1)
GB_HOL = _make_holidays(_yrs, _hol_df, 'GB')
FR_HOL = _make_holidays(_yrs, _hol_df, 'France')

# ── 4. Full pipeline: OLS → jump filter → NLS → X_t ──────────────────────
def build_Xt(hourly_spread, label):
    idx  = hourly_spread.index
    tau  = (pd.DatetimeIndex(idx) - t0).total_seconds() / (365.25 * 24 * 3600)
    dt   = pd.DatetimeIndex(idx).normalize()
    D_t  = ((pd.DatetimeIndex(idx).dayofweek >= 5) | dt.isin(GB_HOL) | dt.isin(FR_HOL)).astype(float)
    feat = pd.DataFrame({'const': 1.0, 'tau': tau,
                         'sin1': np.sin(2*np.pi*tau), 'cos1': np.cos(2*np.pi*tau),
                         'D_t': D_t}, index=idx)
    hrs = pd.DatetimeIndex(idx).hour
    for h in range(0, 23):
        feat[f'H{h+1:02d}'] = np.where(hrs == h, 1, np.where(hrs == 23, -1, 0)).astype(float)

    ols     = sm.OLS(hourly_spread.values, feat).fit()
    resid_h = hourly_spread - pd.Series(ols.fittedvalues, index=idx)
    resid_s = resid_h.resample('D').mean().dropna()

    # OLS CI half-width for Cartea step 2
    Q, _ = np.linalg.qr(feat.values.astype(float), mode='reduced')
    lev  = (Q ** 2).sum(axis=1)
    ci_h = pd.Series(1.96 * np.sqrt(lev * float(ols.mse_resid)), index=idx)
    ci_d = ci_h.resample('D').mean()

    # Cartea jump filter
    delta   = resid_s.diff().dropna()
    clean_d = delta.copy()
    for _ in range(20):
        mu, sg = clean_d.mean(), clean_d.std()
        mask = (clean_d - mu).abs() > 3.0 * sg
        if not mask.any():
            break
        clean_d[mask] = np.nan
    cand = delta.index[delta.index.isin(clean_d[clean_d.isna()].index)]
    confirmed = [d for d in cand if (
        (delta[d] > 0 and resid_s[d] > float(ci_d[d]) if d in ci_d.index else 0.0) or
        (delta[d] < 0 and resid_s[d] < -float(ci_d[d]) if d in ci_d.index else 0.0))]
    jumps = resid_s[resid_s.index.isin(confirmed)]

    # NLS OU+jump
    all_dates = resid_s.index
    s_tilde   = resid_s.values.astype(float)
    n_d       = len(s_tilde)
    d_rs      = resid_s.diff()
    jpos, jsz = [], []
    for d in sorted(jumps.index):
        p  = int(all_dates.get_loc(d))
        sz = float(d_rs[d]) if p > 0 and pd.notna(d_rs.get(d)) else float(resid_s[d])
        jpos.append(p); jsz.append(sz)
    jpos = np.array(jpos, dtype=int)
    jsz  = np.array(jsz,  dtype=float)

    def recon_Y(phi_Y):
        Y = np.zeros(n_d)
        for jp, js in zip(jpos, jsz):
            t_idx = np.arange(jp, n_d)
            Y[t_idx] += js * phi_Y ** (t_idx - jp)
        return Y

    def obj(beta_yr):
        phi_Y = np.exp(-beta_yr / 365.25)
        Y     = recon_Y(phi_Y)
        Xv    = s_tilde - Y
        A     = np.column_stack([np.ones(n_d - 1), Xv[:-1]])
        c, *_ = np.linalg.lstsq(A, Xv[1:], rcond=None)
        return float(np.mean((Xv[1:] - A @ c) ** 2))

    res   = minimize_scalar(obj, bounds=(1.0, 5000.0), method='bounded')
    phi_Y = np.exp(-res.x / 365.25)
    X_t   = s_tilde - recon_Y(phi_Y)

    A = np.column_stack([np.ones(n_d - 1), X_t[:-1]])
    c, *_ = np.linalg.lstsq(A, X_t[1:], rcond=None)
    phi_hat = float(c[1])
    kappa   = -np.log(max(phi_hat, 1e-9)) * 365.25
    hl      = np.log(2) / kappa * 365.25

    print(f'\n[{label}]')
    print(f'  Days: {n_d}  |  Jumps: {len(jumps)} ({len(jumps)/n_d*100:.1f}%)')
    print(f'  phi={phi_hat:.4f}  kappa={kappa:.1f}/yr  half-life={hl:.2f} days')
    return X_t, phi_hat, hl, all_dates

hourly_full = panel['spread_gbp'].dropna()
Xt_f, phi_f, hl_f, dates_f = build_Xt(hourly_full, 'FULL  (Dec 2021 – Jul 2026)')

hourly_post = hourly_full[hourly_full.index >= '2023-01-01']
Xt_p, phi_p, hl_p, dates_p = build_Xt(hourly_post, 'POST  (Jan 2023 – Jul 2026)')

# ── 5. ACF table ──────────────────────────────────────────────────────────
MAX_LAG  = 60
LAGS_PRN = [1, 2, 3, 5, 7, 10, 15, 20, 30, 45, 60]
lags_arr = np.arange(MAX_LAG + 1)

acf_f, ci_f = acf(Xt_f, nlags=MAX_LAG, alpha=0.05, fft=True)
acf_p, ci_p = acf(Xt_p, nlags=MAX_LAG, alpha=0.05, fft=True)
theo_f = phi_f ** lags_arr
theo_p = phi_p ** lags_arr

print(f'\n{"Lag":>5}  '
      f'{"Full ACF":>9}  {"Full φ^k":>9}  {"Post ACF":>9}  {"Post φ^k":>9}  {"Excess (full)?"}')
print('-' * 72)
for k in LAGS_PRN:
    ci95_f = float(ci_f[k, 1]) - float(acf_f[k])
    excess = '*' if acf_f[k] > theo_f[k] + ci95_f else ''
    print(f'{k:>5}  {acf_f[k]:>9.4f}  {theo_f[k]:>9.4f}  '
          f'{acf_p[k]:>9.4f}  {theo_p[k]:>9.4f}  {excess}')

# ── 6. Ljung-Box ──────────────────────────────────────────────────────────
LB_LAGS = [5, 10, 20, 30]
lb_lev_f = acorr_ljungbox(Xt_f, lags=LB_LAGS, return_df=True)
lb_lev_p = acorr_ljungbox(Xt_p, lags=LB_LAGS, return_df=True)
lb_sq_f  = acorr_ljungbox(Xt_f ** 2, lags=LB_LAGS, return_df=True)
lb_sq_p  = acorr_ljungbox(Xt_p ** 2, lags=LB_LAGS, return_df=True)

print('\nLjung-Box X_t levels:')
print(f'  {"Lag":>5}  {"Full stat":>10}  {"Full p":>8}  {"Post stat":>10}  {"Post p":>8}')
for lag in LB_LAGS:
    print(f'  {lag:>5}  {lb_lev_f.loc[lag,"lb_stat"]:>10.1f}  '
          f'{lb_lev_f.loc[lag,"lb_pvalue"]:>8.4f}  '
          f'{lb_lev_p.loc[lag,"lb_stat"]:>10.1f}  '
          f'{lb_lev_p.loc[lag,"lb_pvalue"]:>8.4f}')

print('\nLjung-Box X_t^2 (volatility clustering):')
print(f'  {"Lag":>5}  {"Full stat":>10}  {"Full p":>8}  {"Post stat":>10}  {"Post p":>8}')
for lag in LB_LAGS:
    print(f'  {lag:>5}  {lb_sq_f.loc[lag,"lb_stat"]:>10.1f}  '
          f'{lb_sq_f.loc[lag,"lb_pvalue"]:>8.4f}  '
          f'{lb_sq_p.loc[lag,"lb_stat"]:>10.1f}  '
          f'{lb_sq_p.loc[lag,"lb_pvalue"]:>8.4f}')

# ── 7. Plot ───────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 9))
titles   = [f'Full sample (Dec 2021 – Jul 2026)\nφ={phi_f:.3f}, HL={hl_f:.1f}d',
            f'Post-crisis (Jan 2023 – Jul 2026)\nφ={phi_p:.3f}, HL={hl_p:.1f}d']
datasets = [(Xt_f, phi_f, ci_f, acf_f, theo_f),
            (Xt_p, phi_p, ci_p, acf_p, theo_p)]

for col, (Xt, phi, ci_lev, acf_lev, theo) in enumerate(datasets):
    acf_sq, ci_sq = acf(Xt ** 2, nlags=MAX_LAG, alpha=0.05, fft=True)

    ax = axes[0, col]
    ax.bar(lags_arr, acf_lev, color='steelblue', alpha=0.55, width=0.8,
           label='Empirical ACF(X_t)')
    ax.plot(lags_arr, theo, 'r-', lw=2, label=f'AR(1) φ^k')
    ax.fill_between(lags_arr, ci_lev[:, 0], ci_lev[:, 1],
                    alpha=0.18, color='grey', label='95% CI')
    ax.axhline(0, color='k', lw=0.5)
    ax.set_title(f'ACF(X_t) — levels\n{titles[col]}', fontweight='bold')
    ax.set_ylabel('Autocorrelation'); ax.set_xlim(-1, MAX_LAG + 1)
    ax.legend(fontsize=8)

    ax2 = axes[1, col]
    ax2.bar(lags_arr, acf_sq, color='darkorange', alpha=0.55, width=0.8,
            label='Empirical ACF(X_t²)')
    ax2.fill_between(lags_arr, ci_sq[:, 0], ci_sq[:, 1],
                     alpha=0.18, color='grey', label='95% CI')
    ax2.axhline(0, color='k', lw=0.5)
    ax2.set_title(f'ACF(X_t²) — volatility clustering\n{titles[col]}', fontweight='bold')
    ax2.set_xlabel('Lag (days)'); ax2.set_ylabel('Autocorrelation')
    ax2.set_xlim(-1, MAX_LAG + 1); ax2.legend(fontsize=8)

plt.tight_layout()
plt.savefig(OUT_PATH, dpi=150, bbox_inches='tight')
print(f'\nPlot saved → {OUT_PATH}')

# ── 8. Interpretation ─────────────────────────────────────────────────────
print('\n── Interpretation ─────────────────────────────────────────────────')
lev_ok_f = all(float(lb_lev_f.loc[lag, 'lb_pvalue']) > 0.05 for lag in LB_LAGS)
lev_ok_p = all(float(lb_lev_p.loc[lag, 'lb_pvalue']) > 0.05 for lag in LB_LAGS)
sq_ok_f  = all(float(lb_sq_f.loc[lag,  'lb_pvalue']) > 0.05 for lag in LB_LAGS)
sq_ok_p  = all(float(lb_sq_p.loc[lag,  'lb_pvalue']) > 0.05 for lag in LB_LAGS)

for label, lev_ok, sq_ok in [('Full', lev_ok_f, sq_ok_f), ('Post', lev_ok_p, sq_ok_p)]:
    print(f'\n  [{label} sample]')
    if lev_ok:
        print('    LEVELS OK: AR(1) correctly specified. No excess memory.')
    else:
        print('    LEVELS FAIL: significant autocorrelation beyond AR(1).')
        print('    → Consider re-estimating phi on post-crisis window or 2-state HMM.')
    if sq_ok:
        print('    SQUARED OK: no volatility clustering detected.')
    else:
        print('    SQUARED: volatility clustering present.')
        print('    → GARCH(1,1) warranted (note: higher sigma raises |spread| — '
              'does not worsen floor risk).')
print('───────────────────────────────────────────────────────────────────')
