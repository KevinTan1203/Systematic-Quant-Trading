# ============================================================
# QUANTITATIVE TRADING STRATEGY ASSESSMENT
# Instrument: Minute-bar OHLCV data (2024-07-11 to 2025-04-30)
# Assumed: Natural Gas Futures or similar commodity (negative prices possible)
# ============================================================

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.dates import DateFormatter
import seaborn as sns
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (accuracy_score, precision_score, recall_score, 
                              f1_score, roc_auc_score, confusion_matrix, 
                              classification_report)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
import xgboost as xgb
import lightgbm as lgb
import os

# ---- Setup ----
os.makedirs('/home/claude/figs', exist_ok=True)
plt.style.use('seaborn-v0_8-darkgrid')
COLORS = {'bull': '#2ecc71', 'bear': '#e74c3c', 'neutral': '#3498db', 
          'accent': '#f39c12', 'dark': '#2c3e50', 'light': '#ecf0f1'}

# ============================================================
# 1. DATA LOADING & CLEANING
# ============================================================
print("=" * 60)
print("LOADING & CLEANING DATA")
print("=" * 60)

df_raw = pd.read_csv('/mnt/user-data/uploads/Data_1_longmin.csv')
df_raw['date'] = pd.to_datetime(df_raw['date'])
df_raw = df_raw.sort_values('date').reset_index(drop=True)

print(f"Raw shape: {df_raw.shape}")
print(f"Date range: {df_raw['date'].min()} to {df_raw['date'].max()}")
print(f"Columns: {df_raw.columns.tolist()}")
print(f"Volume unique values: {df_raw['volume'].unique()}")
print(f"Period unique values: {df_raw['period'].unique()}")
print(f"Missing values:\n{df_raw.isnull().sum()}")
print(f"Negative close prices: {(df_raw['close'] < 0).sum()}")
print(f"Negative open prices: {(df_raw['open'] < 0).sum()}")

# OHLC consistency check
ohlc_violations = (
    (df_raw['high'] < df_raw['low']).sum() +
    (df_raw['high'] < df_raw['open']).sum() +
    (df_raw['high'] < df_raw['close']).sum() +
    (df_raw['low'] > df_raw['open']).sum() +
    (df_raw['low'] > df_raw['close']).sum()
)
print(f"OHLC consistency violations: {ohlc_violations}")

# Gap analysis
df_raw['gap_min'] = df_raw['date'].diff().dt.total_seconds() / 60
print(f"\nGap analysis (minutes):")
print(df_raw['gap_min'].describe())
large_gaps = df_raw[df_raw['gap_min'] > 60]
print(f"Gaps > 1 hour: {len(large_gaps)}")

# Working dataset: keep as-is (negative prices are valid for spread/basis instruments)
df = df_raw.copy()
df = df.drop(columns=['volume', 'period'])  # volume is 0 throughout; period is always 1

print(f"\nWorking dataset shape: {df.shape}")
"""
Output

============================================================
LOADING & CLEANING DATA
============================================================
Raw shape: (269453, 7)
Date range: 2024-07-11 22:53:00 to 2025-04-30 23:59:00
Columns: ['date', 'open', 'high', 'low', 'close', 'volume', 'period']
Volume unique values: [0]
Period unique values: [1]
Missing values:
date      0
open      0
high      0
low       0
close     0
volume    0
period    0
dtype: int64
Negative close prices: 3898
Negative open prices: 3906
OHLC consistency violations: 0

Gap analysis (minutes):
count    269452.000000
mean          1.566090
std          41.340322
min           1.000000
25%           1.000000
50%           1.000000
75%           1.000000
max        9073.000000
Name: gap_min, dtype: float64
Gaps > 1 hour: 209

Working dataset shape: (269453, 6)
"""


# ============================================================
# 2. EXPLORATORY DATA ANALYSIS - VISUALIZATIONS
# ============================================================
print("\n" + "=" * 60)
print("EXPLORATORY DATA ANALYSIS")
print("=" * 60)

# --- Fig 1: Price time-series overview ---
fig, axes = plt.subplots(3, 1, figsize=(16, 12))
fig.suptitle('EDA – Price Overview & Returns Distribution', fontsize=15, fontweight='bold')

# Close price
axes[0].plot(df['date'], df['close'], color=COLORS['neutral'], lw=0.5, alpha=0.8)
axes[0].axhline(0, color='red', lw=0.8, ls='--', alpha=0.5)
axes[0].set_title('Close Price (1-min bars)', fontsize=12)
axes[0].set_ylabel('Price')

# Rolling 24h stats
df['ret'] = df['close'].pct_change()
# Handle inf due to near-zero prices
df['ret'] = df['ret'].replace([np.inf, -np.inf], np.nan)

# Log returns where possible
df['log_ret'] = np.where(
    (df['close'] > 0) & (df['close'].shift(1) > 0),
    np.log(df['close'] / df['close'].shift(1)),
    np.nan
)

rolling_vol = df['ret'].rolling(60*24).std() * np.sqrt(60*24*252)  # annualized
axes[1].plot(df['date'], rolling_vol, color=COLORS['accent'], lw=0.8)
axes[1].set_title('Rolling 24h Annualized Volatility', fontsize=12)
axes[1].set_ylabel('Ann. Vol')

# Return distribution
ret_clean = df['ret'].dropna()
ret_clean = ret_clean[np.abs(ret_clean) < ret_clean.quantile(0.999)]
axes[2].hist(ret_clean, bins=200, color=COLORS['neutral'], alpha=0.7, edgecolor='none')
axes[2].set_title(f'1-min Return Distribution | Skew={ret_clean.skew():.3f}, Kurt={ret_clean.kurtosis():.3f}', fontsize=12)
axes[2].set_ylabel('Frequency')
axes[2].set_xlabel('Return')

plt.tight_layout()
plt.savefig('/home/claude/figs/fig1_price_overview.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved fig1_price_overview.png")

# Return stats
print(f"\nReturn statistics:")
print(f"  Mean 1-min return: {ret_clean.mean()*100:.4f}%")
print(f"  Std 1-min return:  {ret_clean.std()*100:.4f}%")
print(f"  Skewness:          {ret_clean.skew():.4f}")
print(f"  Kurtosis:          {ret_clean.kurtosis():.4f}")
_, pval = stats.normaltest(ret_clean.sample(5000, random_state=42))
print(f"  Normality p-val:   {pval:.2e} (reject normality: {pval<0.05})")

"""
25%           1.000000
50%           1.000000
75%           1.000000
max        9073.000000
Name: gap_min, dtype: float64
Gaps > 1 hour: 209

Working dataset shape: (269453, 6)

============================================================
EXPLORATORY DATA ANALYSIS
============================================================
Saved fig1_price_overview.png

Return statistics:
  Mean 1-min return: -0.1012%
  Std 1-min return:  9.6183%
  Skewness:          -1.2843
  Kurtosis:          216.4010
  Normality p-val:   0.00e+00 (reject normality: True)
"""


# --- Fig 2: Monthly price heatmap + intraday seasonality ---
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle('EDA – Seasonality & Correlations', fontsize=15, fontweight='bold')

df['hour'] = df['date'].dt.hour
df['dayofweek'] = df['date'].dt.dayofweek
df['month'] = df['date'].dt.month

# Intraday return by hour
hourly_ret = df.groupby('hour')['ret'].mean() * 100
axes[0,0].bar(hourly_ret.index, hourly_ret.values, color=[COLORS['bull'] if v > 0 else COLORS['bear'] for v in hourly_ret.values])
axes[0,0].set_title('Average 1-min Return by Hour of Day', fontsize=11)
axes[0,0].set_xlabel('Hour (UTC)')
axes[0,0].set_ylabel('Avg Return (%)')
axes[0,0].axhline(0, color='black', lw=0.8)

# Intraday volatility by hour
hourly_vol = df.groupby('hour')['ret'].std() * 100
axes[0,1].bar(hourly_vol.index, hourly_vol.values, color=COLORS['accent'])
axes[0,1].set_title('Avg 1-min Volatility by Hour of Day', fontsize=11)
axes[0,1].set_xlabel('Hour (UTC)')
axes[0,1].set_ylabel('Std Dev Return (%)')

# Day-of-week return
dow_ret = df.groupby('dayofweek')['ret'].mean() * 100
dow_labels = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
axes[1,0].bar(range(len(dow_ret)), dow_ret.values, color=[COLORS['bull'] if v > 0 else COLORS['bear'] for v in dow_ret.values])
axes[1,0].set_xticks(range(len(dow_ret)))
axes[1,0].set_xticklabels([dow_labels[i] for i in dow_ret.index])
axes[1,0].set_title('Average Return by Day of Week', fontsize=11)
axes[1,0].set_ylabel('Avg Return (%)')
axes[1,0].axhline(0, color='black', lw=0.8)

# Monthly boxplot of close prices
monthly_data = [df[df['month']==m]['close'].values for m in sorted(df['month'].unique())]
month_labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
present_months = sorted(df['month'].unique())
axes[1,1].boxplot(monthly_data, labels=[month_labels[m-1] for m in present_months], 
                  patch_artist=True, boxprops=dict(facecolor=COLORS['neutral'], alpha=0.6))
axes[1,1].set_title('Price Distribution by Month', fontsize=11)
axes[1,1].set_ylabel('Close Price')
axes[1,1].axhline(0, color='red', lw=0.8, ls='--', alpha=0.5)

plt.tight_layout()
plt.savefig('/home/claude/figs/fig2_seasonality.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved fig2_seasonality.png")

# Autocorrelation
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.stattools import acf

ret_nonan = df['ret'].fillna(0)
lag_acf = acf(ret_nonan, nlags=60, fft=True)
print(f"\nReturn autocorrelation (lag 1-5): {lag_acf[1:6].round(4)}")

# Absolute return (volatility clustering)
abs_acf = acf(ret_nonan.abs(), nlags=60, fft=True)
print(f"Abs return autocorrelation (lag 1-5): {abs_acf[1:6].round(4)}")

"""
Return statistics:
  Mean 1-min return: -0.1012%
  Std 1-min return:  9.6183%
  Skewness:          -1.2843
  Kurtosis:          216.4010
  Normality p-val:   0.00e+00 (reject normality: True)
Saved fig2_seasonality.png

Return autocorrelation (lag 1-5): [-0.0005 -0.0055 -0.0146 -0.0048 -0.0026]
Abs return autocorrelation (lag 1-5): [0.0922 0.1058 0.1047 0.0885 0.1135]
"""


# ============================================================
# 3. FEATURE ENGINEERING (shared by rule-based + ML)
# ============================================================
print("\n" + "=" * 60)
print("FEATURE ENGINEERING")
print("=" * 60)

def add_features(df):
    d = df.copy()
    c = d['close']
    
    # ---- Price-action features ----
    d['bar_range']      = d['high'] - d['low']
    d['bar_body']       = d['close'] - d['open']
    d['bar_body_pct']   = d['bar_body'] / d['bar_range'].replace(0, np.nan)
    d['upper_wick']     = d['high'] - d[['open','close']].max(axis=1)
    d['lower_wick']     = d[['open','close']].min(axis=1) - d['low']
    
    # ---- Returns ----
    for n in [1, 5, 15, 30, 60]:
        d[f'ret_{n}'] = c.pct_change(n)
    
    # ---- Moving averages ----
    for n in [5, 15, 30, 60, 120]:
        d[f'sma_{n}'] = c.rolling(n).mean()
    
    d['sma_cross_5_30']  = d['sma_5'] - d['sma_30']
    d['sma_cross_15_60'] = d['sma_15'] - d['sma_60']
    d['price_vs_sma60']  = (c - d['sma_60']) / d['sma_60'].replace(0, np.nan)
    
    # ---- Momentum / RSI ----
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    d['rsi_14'] = 100 - (100 / (1 + rs))
    
    # ---- Volatility ----
    for n in [15, 30, 60]:
        d[f'vol_{n}'] = d['ret_1'].rolling(n).std()
    
    # ATR
    tr1 = d['high'] - d['low']
    tr2 = (d['high'] - c.shift()).abs()
    tr3 = (d['low']  - c.shift()).abs()
    d['atr_14'] = pd.concat([tr1,tr2,tr3],axis=1).max(axis=1).rolling(14).mean()
    
    # ---- Bollinger Bands ----
    d['bb_mid']   = c.rolling(20).mean()
    bb_std        = c.rolling(20).std()
    d['bb_upper'] = d['bb_mid'] + 2*bb_std
    d['bb_lower'] = d['bb_mid'] - 2*bb_std
    d['bb_pct']   = (c - d['bb_lower']) / (d['bb_upper'] - d['bb_lower']).replace(0,np.nan)
    d['bb_width']  = (d['bb_upper'] - d['bb_lower']) / d['bb_mid'].replace(0,np.nan)
    
    # ---- MACD ----
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    d['macd']        = ema12 - ema26
    d['macd_signal'] = d['macd'].ewm(span=9, adjust=False).mean()
    d['macd_hist']   = d['macd'] - d['macd_signal']
    
    # ---- Time features ----
    d['hour']      = d['date'].dt.hour
    d['minute']    = d['date'].dt.minute
    d['dayofweek'] = d['date'].dt.dayofweek
    
    # ---- Target: next-bar direction ----
    d['fwd_ret_1']  = c.shift(-1) / c - 1
    d['fwd_ret_5']  = c.shift(-5) / c - 1
    d['fwd_ret_15'] = c.shift(-15) / c - 1
    d['target']     = (d['fwd_ret_5'] > 0).astype(int)  # 1=up, 0=down/flat in next 5 bars
    
    return d

df = add_features(df)
print(f"Feature-engineered shape: {df.shape}")

# Drop rows where we don't have targets (last 5 rows) or insufficient lookback
df_model = df.dropna(subset=['target', 'rsi_14', 'sma_cross_15_60', 'fwd_ret_5']).copy()
# Replace inf
df_model = df_model.replace([np.inf, -np.inf], np.nan)

# For features requiring valid prices, remove near-zero close rows for ret-based features
print(f"Model-ready shape: {df_model.shape}")
print(f"Target balance: {df_model['target'].value_counts().to_dict()}")

"""
Return autocorrelation (lag 1-5): [-0.0005 -0.0055 -0.0146 -0.0048 -0.0026]
Abs return autocorrelation (lag 1-5): [0.0922 0.1058 0.1047 0.0885 0.1135]

============================================================
FEATURE ENGINEERING
============================================================
Feature-engineered shape: (269453, 47)
Model-ready shape: (269375, 47)
Target balance: {0: 139462, 1: 129913}
"""


# ============================================================
# 4. RULE-BASED STRATEGY
# ============================================================
print("\n" + "=" * 60)
print("RULE-BASED STRATEGY")
print("=" * 60)

# ----- Strategy: Trend-following with RSI Mean-Reversion Filter -----
# RATIONALE:
#   1. The SMA crossover (fast 15 > slow 60) identifies the trend direction.
#   2. RSI filters ensure we do not chase overbought/oversold extremes.
#   3. Bollinger Band %B confirms momentum is not exhausted.
#   4. MACD histogram sign confirms momentum direction.
#   5. Volatility filter avoids trading in extremely quiet markets (low
#      signal-to-noise) and extremely turbulent markets (wide spreads, 
#      gap risk). This is critical given the extreme kurtosis observed.
# 
# POSITION SIZING: 1 unit per trade (notional normalization)
# TRANSACTION COSTS: 0.01 per unit per side (reasonable for futures/spread)
# EXIT: Opposite signal, or stop-loss of 2×ATR from entry
# LOOK-AHEAD BIAS AVOIDANCE: All signals use data available at bar close,
#   trade executes at next bar open.

TC_PER_SIDE = 0.01  # transaction cost per trade side

def rule_based_strategy(df):
    """
    Deterministic rule-based strategy.
    Signals generated at bar close, filled at next bar open.
    """
    d = df.copy().reset_index(drop=True)
    
    # ENTRY CONDITIONS
    # Long: 15-period SMA > 60-period SMA (uptrend)
    #       RSI between 40 and 70 (not oversold/overbought)
    #       MACD histogram positive (momentum confirming)
    #       Bollinger %B between 0.4 and 0.9 (not at extremes)
    #       Volatility in reasonable range (atr_14 > 0.05, < 3×median)
    
    atr_med = d['atr_14'].median()
    
    long_signal = (
        (d['sma_15'] > d['sma_60']) &
        (d['rsi_14'] > 40) & (d['rsi_14'] < 70) &
        (d['macd_hist'] > 0) &
        (d['bb_pct'] > 0.4) & (d['bb_pct'] < 0.9) &
        (d['atr_14'] > 0.05) & (d['atr_14'] < 3 * atr_med)
    )
    
    short_signal = (
        (d['sma_15'] < d['sma_60']) &
        (d['rsi_14'] > 30) & (d['rsi_14'] < 60) &
        (d['macd_hist'] < 0) &
        (d['bb_pct'] > 0.1) & (d['bb_pct'] < 0.6) &
        (d['atr_14'] > 0.05) & (d['atr_14'] < 3 * atr_med)
    )
    
    # Shift by 1: signal at close t, fill at open t+1
    d['long_entry']  = long_signal.shift(1).fillna(False)
    d['short_entry'] = short_signal.shift(1).fillna(False)
    
    # Simulate trades
    positions = []
    equity_curve = []
    pnl_list = []
    trades = []
    
    position = 0      # -1, 0, +1
    entry_price = 0.0
    entry_idx = 0
    stop_price = 0.0
    equity = 0.0
    
    for i in range(1, len(d)):
        open_p  = d.loc[i, 'open']
        close_p = d.loc[i, 'close']
        atr     = d.loc[i, 'atr_14']
        
        bar_pnl = 0.0
        
        if position != 0:
            # Check stop loss (2×ATR from entry)
            if position == 1 and open_p <= stop_price:
                pnl = (stop_price - entry_price) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type': 'long', 'entry': entry_price, 'exit': stop_price, 
                                'pnl': pnl, 'exit_reason': 'stop', 'bars': i - entry_idx})
                position = 0
            elif position == -1 and open_p >= stop_price:
                pnl = (entry_price - stop_price) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type': 'short', 'entry': entry_price, 'exit': stop_price, 
                                'pnl': pnl, 'exit_reason': 'stop', 'bars': i - entry_idx})
                position = 0
        
        if position == 1:
            # Check for exit signal (short or opposite)
            if d.loc[i, 'short_entry'] or not d.loc[i, 'long_entry']:
                pnl = (close_p - entry_price) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type': 'long', 'entry': entry_price, 'exit': close_p, 
                                'pnl': pnl, 'exit_reason': 'signal', 'bars': i - entry_idx})
                position = 0
                
        elif position == -1:
            if d.loc[i, 'long_entry'] or not d.loc[i, 'short_entry']:
                pnl = (entry_price - close_p) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type': 'short', 'entry': entry_price, 'exit': close_p, 
                                'pnl': pnl, 'exit_reason': 'signal', 'bars': i - entry_idx})
                position = 0
        
        if position == 0:
            if d.loc[i, 'long_entry'] and not np.isnan(atr):
                position = 1
                entry_price = open_p
                entry_idx = i
                stop_price = entry_price - 2 * atr
            elif d.loc[i, 'short_entry'] and not np.isnan(atr):
                position = -1
                entry_price = open_p
                entry_idx = i
                stop_price = entry_price + 2 * atr
        
        equity += bar_pnl
        equity_curve.append(equity)
        pnl_list.append(bar_pnl)
    
    return d.iloc[1:].copy(), equity_curve, pnl_list, trades

df_strat, equity_curve, pnl_list, trades = rule_based_strategy(df_model)
print(f"Total trades: {len(trades)}")

trades_df = pd.DataFrame(trades)
if len(trades_df) > 0:
    print(trades_df['pnl'].describe())
    print(f"Win rate: {(trades_df['pnl'] > 0).mean():.3f}")

"""
FEATURE ENGINEERING
============================================================
Feature-engineered shape: (269453, 47)
Model-ready shape: (269375, 47)
Target balance: {0: 139462, 1: 129913}

============================================================
RULE-BASED STRATEGY
============================================================
Total trades: 29267
count    29267.000000
mean        -0.047774
std          0.317073
min        -27.000000
25%         -0.130000
50%         -0.030000
75%          0.060000
max          7.520000
Name: pnl, dtype: float64
Win rate: 0.390
"""

# ---- Performance Metrics ----
def compute_performance(equity_curve, pnl_list, trades_df, bars_per_year=252*24*60, label="Strategy"):
    ec = np.array(equity_curve)
    pnl = np.array(pnl_list)
    
    # Returns series (bar-level)
    bar_rets = pnl  # absolute PnL per bar
    
    total_return = ec[-1]
    n_bars = len(ec)
    years = n_bars / bars_per_year
    ann_return = total_return / years if years > 0 else 0
    
    daily_pnl = pd.Series(pnl).resample('D', origin='start').sum() if False else pd.Series(pnl)
    
    # Sharpe / Sortino on bar-level returns
    bar_mean = np.nanmean(pnl)
    bar_std  = np.nanstd(pnl)
    sharpe_bar = (bar_mean / bar_std) * np.sqrt(bars_per_year) if bar_std > 0 else 0
    
    downside = pnl[pnl < 0]
    sortino_bar = (bar_mean / np.std(downside)) * np.sqrt(bars_per_year) if len(downside) > 0 else 0
    
    # Drawdown
    running_max = np.maximum.accumulate(ec)
    drawdown = ec - running_max
    max_dd = drawdown.min()
    
    # Trade-level stats
    if len(trades_df) > 0:
        win_rate    = (trades_df['pnl'] > 0).mean()
        avg_trade   = trades_df['pnl'].mean()
        gross_profit = trades_df[trades_df['pnl']>0]['pnl'].sum()
        gross_loss   = trades_df[trades_df['pnl']<0]['pnl'].sum().item()
        profit_factor = gross_profit / abs(gross_loss) if gross_loss != 0 else np.inf
        n_trades    = len(trades_df)
    else:
        win_rate = avg_trade = profit_factor = n_trades = 0

    print(f"\n{'='*40}")
    print(f"  PERFORMANCE: {label}")
    print(f"{'='*40}")
    print(f"  Total PnL (abs):       {total_return:>10.4f}")
    print(f"  Ann. PnL:              {ann_return:>10.4f}")
    print(f"  Ann. Sharpe:           {sharpe_bar:>10.4f}")
    print(f"  Ann. Sortino:          {sortino_bar:>10.4f}")
    print(f"  Max Drawdown:          {max_dd:>10.4f}")
    print(f"  Win Rate:              {win_rate:>10.3f}")
    print(f"  Profit Factor:         {profit_factor:>10.4f}")
    print(f"  Avg Trade PnL:         {avg_trade:>10.4f}")
    print(f"  Num Trades:            {n_trades:>10d}")
    print(f"  Backtest years:        {years:>10.2f}")
    
    return dict(total_return=total_return, ann_return=ann_return,
                sharpe=sharpe_bar, sortino=sortino_bar, max_dd=max_dd,
                win_rate=win_rate, profit_factor=profit_factor, 
                avg_trade=avg_trade, n_trades=n_trades, years=years)

rb_perf = compute_performance(equity_curve, pnl_list, trades_df, label="Rule-Based Strategy")

"""
25%         -0.130000
50%         -0.030000
75%          0.060000
max          7.520000
Name: pnl, dtype: float64
Win rate: 0.390

========================================
  PERFORMANCE: Rule-Based Strategy
========================================
  Total PnL (abs):       -1398.1871
  Ann. PnL:              -1883.5305
  Ann. Sharpe:             -29.6195
  Ann. Sortino:            -10.5176
  Max Drawdown:          -1398.9871
  Win Rate:                   0.390
  Profit Factor:             0.5565
  Avg Trade PnL:            -0.0478
  Num Trades:                 29267
  Backtest years:              0.74
"""

# The original rule-based strategy over-trades and loses on TC.
# Refine: Add holding period (minimum 15 bars before re-evaluation) and 
# use less-frequent signals.

def rule_based_v2(df):
    """
    Refined rule-based strategy with:
    - Minimum 15-bar hold
    - Stronger trend filter (5-period return must be positive for long)
    - Exit only on opposing strong signal
    """
    d = df.copy().reset_index(drop=True)
    
    atr_med = d['atr_14'].quantile(0.75)  # use 75th pct as cap
    
    # Stronger entry conditions
    long_signal = (
        (d['sma_15'] > d['sma_60']) &
        (d['sma_30'] > d['sma_120']) &
        (d['rsi_14'] > 45) & (d['rsi_14'] < 65) &
        (d['macd_hist'] > 0) &
        (d['ret_15'] > 0) &
        (d['bb_pct'] > 0.5) & (d['bb_pct'] < 0.85) &
        (d['atr_14'].between(0.10, atr_med))
    )
    
    short_signal = (
        (d['sma_15'] < d['sma_60']) &
        (d['sma_30'] < d['sma_120']) &
        (d['rsi_14'] > 35) & (d['rsi_14'] < 55) &
        (d['macd_hist'] < 0) &
        (d['ret_15'] < 0) &
        (d['bb_pct'] > 0.15) & (d['bb_pct'] < 0.5) &
        (d['atr_14'].between(0.10, atr_med))
    )
    
    # Shift by 1
    long_entry  = long_signal.shift(1).fillna(False)
    short_entry = short_signal.shift(1).fillna(False)
    
    equity_curve, pnl_list, trades = [], [], []
    position = 0
    entry_price = 0.0
    entry_idx = 0
    stop_price = 0.0
    equity = 0.0
    MIN_HOLD = 15
    
    for i in range(1, len(d)):
        open_p  = d.loc[i, 'open']
        close_p = d.loc[i, 'close']
        atr     = d.loc[i, 'atr_14']
        held_bars = i - entry_idx
        bar_pnl = 0.0
        
        if position != 0:
            # Stop loss
            if position == 1 and open_p <= stop_price:
                pnl = (stop_price - entry_price) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type': 'long', 'entry': entry_price, 'exit': stop_price, 
                                'pnl': pnl, 'exit_reason': 'stop', 'bars': held_bars})
                position = 0
            elif position == -1 and open_p >= stop_price:
                pnl = (entry_price - stop_price) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type': 'short', 'entry': entry_price, 'exit': stop_price, 
                                'pnl': pnl, 'exit_reason': 'stop', 'bars': held_bars})
                position = 0
        
        if position == 1 and held_bars >= MIN_HOLD:
            if short_entry.iloc[i]:
                pnl = (close_p - entry_price) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type': 'long', 'entry': entry_price, 'exit': close_p, 
                                'pnl': pnl, 'exit_reason': 'signal', 'bars': held_bars})
                position = 0
        elif position == -1 and held_bars >= MIN_HOLD:
            if long_entry.iloc[i]:
                pnl = (entry_price - close_p) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type': 'short', 'entry': entry_price, 'exit': close_p, 
                                'pnl': pnl, 'exit_reason': 'signal', 'bars': held_bars})
                position = 0
        
        if position == 0:
            atr_val = atr if not np.isnan(atr) else 0.1
            if long_entry.iloc[i]:
                position = 1
                entry_price = open_p
                entry_idx = i
                stop_price = entry_price - 2 * atr_val
            elif short_entry.iloc[i]:
                position = -1
                entry_price = open_p
                entry_idx = i
                stop_price = entry_price + 2 * atr_val
        
        equity += bar_pnl
        equity_curve.append(equity)
        pnl_list.append(bar_pnl)
    
    return equity_curve, pnl_list, pd.DataFrame(trades)

equity_v2, pnl_v2, trades_v2 = rule_based_v2(df_model)
rb_perf2 = compute_performance(equity_v2, pnl_v2, trades_v2, label="Rule-Based Strategy v2 (Refined)")


"""
  Max Drawdown:          -1398.9871
  Win Rate:                   0.390
  Profit Factor:             0.5565
  Avg Trade PnL:            -0.0478
  Num Trades:                 29267
  Backtest years:              0.74

========================================
  PERFORMANCE: Rule-Based Strategy v2 (Refined)
========================================
  Total PnL (abs):        -461.4271
  Ann. PnL:               -621.5993
  Ann. Sharpe:             -12.4711
  Ann. Sortino:             -2.7216
  Max Drawdown:           -461.4271
  Win Rate:                   0.223
  Profit Factor:             0.4047
  Avg Trade PnL:            -0.2097
  Num Trades:                  2200
  Backtest years:              0.74
"""


# Both rule-based variants are losing. The issue: this instrument has
# near-zero to negative prices, extreme kurtosis (216!), and the price 
# trend is clearly downward then mean-reverting. A pure trend-follow 
# struggles. Let's try a MEAN-REVERSION approach which suits instruments
# that oscillate around a drift.

def mean_reversion_strategy(df):
    """
    Mean-reversion strategy:
    - Entry: RSI < 30 (oversold) → Long; RSI > 70 (overbought) → Short
    - Confirmation: Price beyond 2σ Bollinger Band
    - Exit: RSI returns to 50, or price crosses SMA
    - Risk: 2×ATR stop
    - Min hold: 5 bars
    """
    d = df.copy().reset_index(drop=True)
    
    long_entry  = ((d['rsi_14'] < 30) & (d['bb_pct'] < 0.1)).shift(1).fillna(False)
    short_entry = ((d['rsi_14'] > 70) & (d['bb_pct'] > 0.9)).shift(1).fillna(False)
    long_exit   = ((d['rsi_14'] > 50) | (d['close'] > d['sma_30'])).shift(1).fillna(False)
    short_exit  = ((d['rsi_14'] < 50) | (d['close'] < d['sma_30'])).shift(1).fillna(False)
    
    equity_curve, pnl_list, trades = [], [], []
    position = 0
    entry_price = 0.0
    entry_idx = 0
    stop_price = 0.0
    equity = 0.0
    MIN_HOLD = 5
    
    for i in range(1, len(d)):
        open_p  = d.loc[i, 'open']
        close_p = d.loc[i, 'close']
        atr     = d.loc[i, 'atr_14'] if not np.isnan(d.loc[i, 'atr_14']) else 0.1
        held_bars = i - entry_idx
        bar_pnl = 0.0
        
        if position != 0:
            if position == 1 and open_p <= stop_price:
                pnl = (stop_price - entry_price) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type':'long','entry':entry_price,'exit':stop_price,
                                'pnl':pnl,'exit_reason':'stop','bars':held_bars})
                position = 0
            elif position == -1 and open_p >= stop_price:
                pnl = (entry_price - stop_price) - 2*TC_PER_SIDE
                bar_pnl += pnl
                trades.append({'type':'short','entry':entry_price,'exit':stop_price,
                                'pnl':pnl,'exit_reason':'stop','bars':held_bars})
                position = 0
        
        if position == 1 and held_bars >= MIN_HOLD and long_exit.iloc[i]:
            pnl = (close_p - entry_price) - 2*TC_PER_SIDE
            bar_pnl += pnl
            trades.append({'type':'long','entry':entry_price,'exit':close_p,
                            'pnl':pnl,'exit_reason':'signal','bars':held_bars})
            position = 0
        elif position == -1 and held_bars >= MIN_HOLD and short_exit.iloc[i]:
            pnl = (entry_price - close_p) - 2*TC_PER_SIDE
            bar_pnl += pnl
            trades.append({'type':'short','entry':entry_price,'exit':close_p,
                            'pnl':pnl,'exit_reason':'signal','bars':held_bars})
            position = 0
        
        if position == 0:
            if long_entry.iloc[i]:
                position = 1; entry_price = open_p; entry_idx = i
                stop_price = entry_price - 2*atr
            elif short_entry.iloc[i]:
                position = -1; entry_price = open_p; entry_idx = i
                stop_price = entry_price + 2*atr
        
        equity += bar_pnl
        equity_curve.append(equity)
        pnl_list.append(bar_pnl)
    
    return equity_curve, pnl_list, pd.DataFrame(trades)

equity_mr, pnl_mr, trades_mr = mean_reversion_strategy(df_model)
rb_perf_mr = compute_performance(equity_mr, pnl_mr, trades_mr, label="Mean-Reversion Strategy")


"""
  Max Drawdown:           -461.4271
  Win Rate:                   0.223
  Profit Factor:             0.4047
  Avg Trade PnL:            -0.2097
  Num Trades:                  2200
  Backtest years:              0.74

========================================
  PERFORMANCE: Mean-Reversion Strategy
========================================
  Total PnL (abs):         644.2743
  Ann. PnL:                867.9169
  Ann. Sharpe:               9.6904
  Ann. Sortino:              1.8506
  Max Drawdown:            -93.1286
  Win Rate:                   0.627
  Profit Factor:             1.7128
  Avg Trade PnL:             0.1569
  Num Trades:                  4105
  Backtest years:              0.74
"""

# ---- Plot equity curves for all rule-based strategies ----
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle('Rule-Based Strategies – Equity Curves & Trade Analysis', fontsize=15, fontweight='bold')

# Equity curves
ec_arr_mr = np.array(equity_mr)
ec_arr_v1 = np.array(equity_curve)
ec_arr_v2 = np.array(equity_v2)

axes[0,0].plot(ec_arr_v1, color=COLORS['bear'], lw=1, label='Trend v1', alpha=0.8)
axes[0,0].plot(ec_arr_v2, color=COLORS['accent'], lw=1, label='Trend v2', alpha=0.8)
axes[0,0].plot(ec_arr_mr, color=COLORS['bull'], lw=1.5, label='Mean-Rev', alpha=0.9)
axes[0,0].axhline(0, color='black', lw=0.8, ls='--')
axes[0,0].set_title('Equity Curves (all strategies)')
axes[0,0].set_ylabel('Cumulative PnL')
axes[0,0].legend(fontsize=9)

# Mean-Reversion drawdown
running_max = np.maximum.accumulate(ec_arr_mr)
dd_mr = ec_arr_mr - running_max
axes[0,1].fill_between(range(len(dd_mr)), dd_mr, 0, color=COLORS['bear'], alpha=0.5)
axes[0,1].set_title('Mean-Reversion Drawdown')
axes[0,1].set_ylabel('Drawdown')

# Trade PnL distribution (MR strategy)
if len(trades_mr) > 0:
    axes[1,0].hist(trades_mr['pnl'].clip(-2,2), bins=60, color=COLORS['neutral'], alpha=0.7)
    axes[1,0].axvline(0, color='red', lw=1)
    axes[1,0].axvline(trades_mr['pnl'].mean(), color='green', lw=1.5, ls='--', 
                       label=f"Mean={trades_mr['pnl'].mean():.3f}")
    axes[1,0].set_title('Mean-Reversion Trade PnL Distribution')
    axes[1,0].set_xlabel('PnL (clipped at ±2)')
    axes[1,0].legend(fontsize=9)
    
    # Long vs Short breakdown
    type_perf = trades_mr.groupby('type')['pnl'].agg(['mean','sum','count'])
    axes[1,1].bar(type_perf.index, type_perf['mean'], 
                   color=[COLORS['bull'], COLORS['bear']])
    axes[1,1].set_title('Mean-Reversion: Avg PnL by Trade Type')
    axes[1,1].set_ylabel('Average PnL')

plt.tight_layout()
plt.savefig('/home/claude/figs/fig3_equity_curves.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved fig3_equity_curves.png")

"""
  Profit Factor:             1.7128
  Avg Trade PnL:             0.1569
  Num Trades:                  4105
  Backtest years:              0.74
Saved fig3_equity_curves.png
"""


# ============================================================
# 5. MACHINE LEARNING STRATEGY
# ============================================================
print("\n" + "=" * 60)
print("MACHINE LEARNING STRATEGY")
print("=" * 60)

# ---- Feature selection ----
FEATURE_COLS = [
    'bar_range', 'bar_body', 'bar_body_pct', 'upper_wick', 'lower_wick',
    'ret_1', 'ret_5', 'ret_15', 'ret_30', 'ret_60',
    'sma_cross_5_30', 'sma_cross_15_60', 'price_vs_sma60',
    'rsi_14', 'vol_15', 'vol_30', 'vol_60',
    'atr_14', 'bb_pct', 'bb_width',
    'macd', 'macd_signal', 'macd_hist',
    'hour', 'dayofweek'
]

# Remove rows with any NaN in features or target
df_ml = df_model[FEATURE_COLS + ['target', 'date', 'close', 'fwd_ret_5']].dropna().copy()
df_ml = df_ml.replace([np.inf, -np.inf], np.nan).dropna()
df_ml = df_ml.sort_values('date').reset_index(drop=True)
print(f"ML dataset shape: {df_ml.shape}")
print(f"Target distribution: {df_ml['target'].value_counts().to_dict()}")

# ---- Walk-forward split (no data leakage) ----
# Train: first 60% | Val: next 20% | Test: last 20%
n = len(df_ml)
train_end = int(n * 0.60)
val_end   = int(n * 0.80)

X_train = df_ml[FEATURE_COLS].iloc[:train_end]
y_train = df_ml['target'].iloc[:train_end]
X_val   = df_ml[FEATURE_COLS].iloc[train_end:val_end]
y_val   = df_ml['target'].iloc[train_end:val_end]
X_test  = df_ml[FEATURE_COLS].iloc[val_end:]
y_test  = df_ml['target'].iloc[val_end:]

print(f"Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")
print(f"Train date range: {df_ml['date'].iloc[0]} to {df_ml['date'].iloc[train_end-1]}")
print(f"Val date range:   {df_ml['date'].iloc[train_end]} to {df_ml['date'].iloc[val_end-1]}")
print(f"Test date range:  {df_ml['date'].iloc[val_end]} to {df_ml['date'].iloc[-1]}")

# Standardise features (fit only on train)
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train)
X_val_sc   = scaler.transform(X_val)
X_test_sc  = scaler.transform(X_test)

"""
  Profit Factor:             1.7128
  Avg Trade PnL:             0.1569
  Num Trades:                  4105
  Backtest years:              0.74
Saved fig3_equity_curves.png

============================================================
MACHINE LEARNING STRATEGY
============================================================
ML dataset shape: (266392, 29)
Target distribution: {0: 137881, 1: 128511}
Train: 159,835 | Val: 53,278 | Test: 53,279
Train date range: 2024-07-11 23:53:00 to 2025-01-10 11:57:00
Val date range:   2025-01-10 11:58:00 to 2025-03-06 10:13:00
Test date range:  2025-03-06 10:14:00 to 2025-04-30 23:54:00
"""


# ---- Model 1: Logistic Regression ----
print("\n--- Logistic Regression ---")
lr = LogisticRegression(C=0.1, max_iter=500, random_state=42)
lr.fit(X_train_sc, y_train)
lr_val_pred  = lr.predict(X_val_sc)
lr_val_prob  = lr.predict_proba(X_val_sc)[:,1]
lr_test_pred = lr.predict(X_test_sc)
lr_test_prob = lr.predict_proba(X_test_sc)[:,1]
print(f"Val  Acc={accuracy_score(y_val,lr_val_pred):.4f}  AUC={roc_auc_score(y_val,lr_val_prob):.4f}")
print(f"Test Acc={accuracy_score(y_test,lr_test_pred):.4f}  AUC={roc_auc_score(y_test,lr_test_prob):.4f}")

# ---- Model 2: Random Forest ----
print("\n--- Random Forest ---")
rf = RandomForestClassifier(n_estimators=100, max_depth=8, min_samples_leaf=50,
                             random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)
rf_val_pred  = rf.predict(X_val)
rf_val_prob  = rf.predict_proba(X_val)[:,1]
rf_test_pred = rf.predict(X_test)
rf_test_prob = rf.predict_proba(X_test)[:,1]
print(f"Val  Acc={accuracy_score(y_val,rf_val_pred):.4f}  AUC={roc_auc_score(y_val,rf_val_prob):.4f}")
print(f"Test Acc={accuracy_score(y_test,rf_test_pred):.4f}  AUC={roc_auc_score(y_test,rf_test_prob):.4f}")

# ---- Model 3: LightGBM ----
print("\n--- LightGBM ---")
lgbm = lgb.LGBMClassifier(
    n_estimators=300, learning_rate=0.05, max_depth=6,
    num_leaves=31, min_child_samples=100,
    subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=0.1,
    random_state=42, n_jobs=-1, verbose=-1
)
lgbm.fit(X_train, y_train,
         eval_set=[(X_val, y_val)],
         callbacks=[lgb.early_stopping(30, verbose=False)])
lgbm_val_pred  = lgbm.predict(X_val)
lgbm_val_prob  = lgbm.predict_proba(X_val)[:,1]
lgbm_test_pred = lgbm.predict(X_test)
lgbm_test_prob = lgbm.predict_proba(X_test)[:,1]
print(f"Val  Acc={accuracy_score(y_val,lgbm_val_pred):.4f}  AUC={roc_auc_score(y_val,lgbm_val_prob):.4f}")
print(f"Test Acc={accuracy_score(y_test,lgbm_test_pred):.4f}  AUC={roc_auc_score(y_test,lgbm_test_prob):.4f}")

# ---- Model 4: XGBoost ----
print("\n--- XGBoost ---")
xgb_model = xgb.XGBClassifier(
    n_estimators=300, learning_rate=0.05, max_depth=5,
    subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=1.0,
    eval_metric='logloss', random_state=42, n_jobs=-1,
    verbosity=0
)
xgb_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False,
              early_stopping_rounds=30)
xgb_val_pred  = xgb_model.predict(X_val)
xgb_val_prob  = xgb_model.predict_proba(X_val)[:,1]
xgb_test_pred = xgb_model.predict(X_test)
xgb_test_prob = xgb_model.predict_proba(X_test)[:,1]
print(f"Val  Acc={accuracy_score(y_val,xgb_val_pred):.4f}  AUC={roc_auc_score(y_val,xgb_val_prob):.4f}")
print(f"Test Acc={accuracy_score(y_test,xgb_test_pred):.4f}  AUC={roc_auc_score(y_test,xgb_test_prob):.4f}")

"""
Train: 159,835 | Val: 53,278 | Test: 53,279
Train date range: 2024-07-11 23:53:00 to 2025-01-10 11:57:00
Val date range:   2025-01-10 11:58:00 to 2025-03-06 10:13:00
Test date range:  2025-03-06 10:14:00 to 2025-04-30 23:54:00
--- Logistic Regression ---
Val  Acc=0.5165  AUC=0.5217
Test Acc=0.5594  AUC=0.5821
--- Random Forest ---
Val  Acc=0.5297  AUC=0.5365
Test Acc=0.5671  AUC=0.5875
--- LightGBM ---
Val  Acc=0.5185  AUC=0.5278
Test Acc=0.5459  AUC=0.5792
--- XGBoost ---
"""


# ---- ML-based trading backtest (use best model: Random Forest on test set) ----
print("\n" + "=" * 60)
print("ML TRADING BACKTEST (Random Forest - Best Model)")
print("=" * 60)

def ml_trading_backtest(df_section, probs, threshold_long=0.58, threshold_short=0.42):
    """
    Use ML probability to generate long/short signals.
    threshold_long:  P(up) > 0.58 → go long next bar
    threshold_short: P(up) < 0.42 → go short next bar
    """
    d = df_section.reset_index(drop=True)
    
    equity_curve, pnl_list, trades = [], [], []
    position = 0
    entry_price = 0.0
    entry_idx = 0
    equity = 0.0
    MIN_HOLD = 5
    
    # Shift probs by 1 (predict at close, execute at next open)
    probs_shifted = np.concatenate([[0.5], probs[:-1]])
    
    for i in range(1, len(d)):
        open_p  = d.loc[i, 'open'] if 'open' in d.columns else d.loc[i, 'close']
        close_p = d.loc[i, 'close']
        prob    = probs_shifted[i]
        held    = i - entry_idx
        bar_pnl = 0.0
        
        # Exit on opposite signal after min hold
        if position == 1 and held >= MIN_HOLD and prob < threshold_short:
            pnl = (close_p - entry_price) - 2*TC_PER_SIDE
            bar_pnl += pnl
            trades.append({'type':'long','entry':entry_price,'exit':close_p,'pnl':pnl,'bars':held})
            position = 0
        elif position == -1 and held >= MIN_HOLD and prob > threshold_long:
            pnl = (entry_price - close_p) - 2*TC_PER_SIDE
            bar_pnl += pnl
            trades.append({'type':'short','entry':entry_price,'exit':close_p,'pnl':pnl,'bars':held})
            position = 0
        
        if position == 0:
            if prob > threshold_long:
                position = 1; entry_price = open_p; entry_idx = i
            elif prob < threshold_short:
                position = -1; entry_price = open_p; entry_idx = i
        
        equity += bar_pnl
        equity_curve.append(equity)
        pnl_list.append(bar_pnl)
    
    return equity_curve, pnl_list, pd.DataFrame(trades)

# Use test set
test_section = df_ml.iloc[val_end:].reset_index(drop=True)
# Merge close/open back
ec_ml, pnl_ml, trades_ml = ml_trading_backtest(test_section, rf_test_prob)
ml_perf = compute_performance(ec_ml, pnl_ml, trades_ml, label="ML Strategy (RF, Test Set)")

# Also run MR strategy on same test period for comparison
mr_test_section = df_model[df_model['date'] >= df_ml['date'].iloc[val_end]].reset_index(drop=True)
ec_mr_test, pnl_mr_test, trades_mr_test = mean_reversion_strategy(mr_test_section)
mr_perf_test = compute_performance(ec_mr_test, pnl_mr_test, trades_mr_test, label="MR Strategy (Test Period)")

"""
Total trades: 29267
Win rate: 0.390
  PERFORMANCE: Rule-Based Strategy
  Total PnL (abs):       -1398.1871
  Ann. PnL:              -1883.5305
  Ann. Sharpe:             -29.6195
  Ann. Sortino:            -10.5176
  Max Drawdown:          -1398.9871
  Win Rate:                   0.390
  Profit Factor:             0.5565
  Avg Trade PnL:            -0.0478
  Num Trades:                 29267
  Backtest years:              0.74
  PERFORMANCE: Rule-Based Strategy v2 (Refined)
  Total PnL (abs):        -461.4271
  Ann. PnL:               -621.5993
  Ann. Sharpe:             -12.4711
  Ann. Sortino:             -2.7216
  Max Drawdown:           -461.4271
  Win Rate:                   0.223
  Profit Factor:             0.4047
  Avg Trade PnL:            -0.2097
  Num Trades:                  2200
  Backtest years:              0.74
  PERFORMANCE: Mean-Reversion Strategy
  Total PnL (abs):         644.2743
  Ann. PnL:                867.9169
  Ann. Sharpe:               9.6904
  Ann. Sortino:              1.8506
  Max Drawdown:            -93.1286
  Win Rate:                   0.627
  Profit Factor:             1.7128
  Avg Trade PnL:             0.1569
  Num Trades:                  4105
  Backtest years:              0.74
"""


# ---- Feature importance ----
fi = pd.Series(rf.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
print("\nTop 10 Feature Importances (RF):")
print(fi.head(10).round(4).to_string())

lgbm_fi = pd.Series(lgbm.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
print("\nTop 10 Feature Importances (LGBM):")
print(lgbm_fi.head(10).round(4).to_string())

# ---- Figures: ML evaluation ----
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle('ML Model Evaluation', fontsize=15, fontweight='bold')

# Feature importance
fi.head(15).plot.barh(ax=axes[0,0], color=COLORS['neutral'])
axes[0,0].set_title('Random Forest Feature Importance (Top 15)')
axes[0,0].invert_yaxis()

# Confusion matrix (RF test)
cm = confusion_matrix(y_test, rf_test_pred)
sns.heatmap(cm, annot=True, fmt='d', ax=axes[0,1], cmap='Blues',
            xticklabels=['Down','Up'], yticklabels=['Down','Up'])
axes[0,1].set_title('RF Confusion Matrix (Test Set)')
axes[0,1].set_ylabel('Actual'); axes[0,1].set_xlabel('Predicted')

# Probability calibration plot
from sklearn.calibration import calibration_curve
prob_true, prob_pred = calibration_curve(y_test, rf_test_prob, n_bins=10)
axes[1,0].plot(prob_pred, prob_true, 's-', color=COLORS['neutral'], label='RF')
prob_true_lgbm, prob_pred_lgbm = calibration_curve(y_test, lgbm_test_prob, n_bins=10)
axes[1,0].plot(prob_pred_lgbm, prob_true_lgbm, 's-', color=COLORS['accent'], label='LGBM')
axes[1,0].plot([0,1],[0,1],'k--', alpha=0.5, label='Perfect')
axes[1,0].set_title('Calibration Curves (Test Set)')
axes[1,0].set_xlabel('Mean Predicted Probability')
axes[1,0].set_ylabel('Fraction of Positives')
axes[1,0].legend(fontsize=9)

# ML equity curve on test
ec_ml_arr = np.array(ec_ml)
ec_mr_arr = np.array(ec_mr_test)
axes[1,1].plot(ec_ml_arr, color=COLORS['accent'], lw=1.5, label=f'ML RF (test)')
axes[1,1].plot(ec_mr_arr, color=COLORS['bull'], lw=1.5, label=f'MR Rule (test)')
axes[1,1].axhline(0, color='black', lw=0.8, ls='--')
axes[1,1].set_title('Test Period: ML vs Mean-Reversion Equity')
axes[1,1].legend(fontsize=9)

plt.tight_layout()
plt.savefig('/home/claude/figs/fig4_ml_evaluation.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved fig4_ml_evaluation.png")

# Summary table
print("\n" + "="*60)
print("STRATEGY COMPARISON SUMMARY")
print("="*60)
summary = pd.DataFrame({
    'Metric': ['Total PnL','Ann. PnL','Sharpe','Sortino','Max DD','Win Rate','Profit Factor','N Trades'],
    'Trend v1': [rb_perf['total_return'], rb_perf['ann_return'], rb_perf['sharpe'],
                  rb_perf['sortino'], rb_perf['max_dd'], rb_perf['win_rate'],
                  rb_perf['profit_factor'], rb_perf['n_trades']],
    'Trend v2': [rb_perf2['total_return'], rb_perf2['ann_return'], rb_perf2['sharpe'],
                  rb_perf2['sortino'], rb_perf2['max_dd'], rb_perf2['win_rate'],
                  rb_perf2['profit_factor'], rb_perf2['n_trades']],
    'Mean-Rev (full)': [rb_perf_mr['total_return'], rb_perf_mr['ann_return'], rb_perf_mr['sharpe'],
                         rb_perf_mr['sortino'], rb_perf_mr['max_dd'], rb_perf_mr['win_rate'],
                         rb_perf_mr['profit_factor'], rb_perf_mr['n_trades']],
    'ML RF (test)': [ml_perf['total_return'], ml_perf['ann_return'], ml_perf['sharpe'],
                      ml_perf['sortino'], ml_perf['max_dd'], ml_perf['win_rate'],
                      ml_perf['profit_factor'], ml_perf['n_trades']],
    'MR (test)': [mr_perf_test['total_return'], mr_perf_test['ann_return'], mr_perf_test['sharpe'],
                   mr_perf_test['sortino'], mr_perf_test['max_dd'], mr_perf_test['win_rate'],
                   mr_perf_test['profit_factor'], mr_perf_test['n_trades']],
})
summary = summary.set_index('Metric')
print(summary.round(3).to_string())



# Fix XGBoost API and re-run from XGBoost onwards
import warnings; warnings.filterwarnings('ignore')
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, confusion_matrix
from sklearn.calibration import calibration_curve
import lightgbm as lgb
import xgboost as xgb
import os

os.makedirs('/home/claude/figs', exist_ok=True)
COLORS = {'bull':'#2ecc71','bear':'#e74c3c','neutral':'#3498db','accent':'#f39c12'}
TC_PER_SIDE = 0.01

# Reload data
df_raw = pd.read_csv('/mnt/user-data/uploads/Data_1_longmin.csv')
df_raw['date'] = pd.to_datetime(df_raw['date'])
df_raw = df_raw.sort_values('date').reset_index(drop=True)
df = df_raw.drop(columns=['volume','period']).copy()

def add_features(df):
    d = df.copy(); c = d['close']
    d['bar_range'] = d['high']-d['low']; d['bar_body'] = d['close']-d['open']
    d['bar_body_pct'] = d['bar_body']/d['bar_range'].replace(0,np.nan)
    d['upper_wick'] = d['high']-d[['open','close']].max(axis=1)
    d['lower_wick'] = d[['open','close']].min(axis=1)-d['low']
    for n in [1,5,15,30,60]: d[f'ret_{n}'] = c.pct_change(n)
    for n in [5,15,30,60,120]: d[f'sma_{n}'] = c.rolling(n).mean()
    d['sma_cross_5_30'] = d['sma_5']-d['sma_30']
    d['sma_cross_15_60'] = d['sma_15']-d['sma_60']
    d['price_vs_sma60'] = (c-d['sma_60'])/d['sma_60'].replace(0,np.nan)
    delta = c.diff(); gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    d['rsi_14'] = 100-(100/(1+gain/loss.replace(0,np.nan)))
    for n in [15,30,60]: d[f'vol_{n}'] = c.pct_change().rolling(n).std()
    tr1=d['high']-d['low']; tr2=(d['high']-c.shift()).abs(); tr3=(d['low']-c.shift()).abs()
    d['atr_14'] = pd.concat([tr1,tr2,tr3],axis=1).max(axis=1).rolling(14).mean()
    d['bb_mid']=c.rolling(20).mean(); bb_std=c.rolling(20).std()
    d['bb_upper']=d['bb_mid']+2*bb_std; d['bb_lower']=d['bb_mid']-2*bb_std
    d['bb_pct']=(c-d['bb_lower'])/(d['bb_upper']-d['bb_lower']).replace(0,np.nan)
    d['bb_width']=(d['bb_upper']-d['bb_lower'])/d['bb_mid'].replace(0,np.nan)
    ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean()
    d['macd']=ema12-ema26; d['macd_signal']=d['macd'].ewm(span=9,adjust=False).mean()
    d['macd_hist']=d['macd']-d['macd_signal']
    d['hour']=d['date'].dt.hour; d['minute']=d['date'].dt.minute; d['dayofweek']=d['date'].dt.dayofweek
    d['fwd_ret_5'] = c.shift(-5)/c-1
    d['target'] = (d['fwd_ret_5'] > 0).astype(int)
    return d

df = add_features(df)
FEAT = ['bar_range','bar_body','bar_body_pct','upper_wick','lower_wick',
        'ret_1','ret_5','ret_15','ret_30','ret_60',
        'sma_cross_5_30','sma_cross_15_60','price_vs_sma60',
        'rsi_14','vol_15','vol_30','vol_60','atr_14','bb_pct','bb_width',
        'macd','macd_signal','macd_hist','hour','dayofweek']

df_ml = df[FEAT+['target','date','close','open']].dropna()
df_ml = df_ml.replace([np.inf,-np.inf],np.nan).dropna().sort_values('date').reset_index(drop=True)
n = len(df_ml)
te, ve = int(n*0.60), int(n*0.80)

X_tr, y_tr = df_ml[FEAT].iloc[:te], df_ml['target'].iloc[:te]
X_va, y_va = df_ml[FEAT].iloc[te:ve], df_ml['target'].iloc[te:ve]
X_te, y_te = df_ml[FEAT].iloc[ve:], df_ml['target'].iloc[ve:]

sc = StandardScaler(); X_tr_sc=sc.fit_transform(X_tr); X_va_sc=sc.transform(X_va); X_te_sc=sc.transform(X_te)

# LR
lr = LogisticRegression(C=0.1,max_iter=500,random_state=42).fit(X_tr_sc,y_tr)
lr_tp=lr.predict_proba(X_te_sc)[:,1]; lr_ta=accuracy_score(y_te,lr.predict(X_te_sc))

# RF
rf = RandomForestClassifier(100,max_depth=8,min_samples_leaf=50,random_state=42,n_jobs=-1).fit(X_tr,y_tr)
rf_tp=rf.predict_proba(X_te)[:,1]; rf_ta=accuracy_score(y_te,rf.predict(X_te))

# LGBM
lgbm = lgb.LGBMClassifier(300,learning_rate=0.05,max_depth=6,num_leaves=31,
    min_child_samples=100,subsample=0.8,colsample_bytree=0.8,random_state=42,n_jobs=-1,verbose=-1)
lgbm.fit(X_tr,y_tr,eval_set=[(X_va,y_va)],callbacks=[lgb.early_stopping(30,verbose=False)])
lgbm_tp=lgbm.predict_proba(X_te)[:,1]; lgbm_ta=accuracy_score(y_te,lgbm.predict(X_te))

# XGBoost (fixed API)
xgb_m = xgb.XGBClassifier(n_estimators=300,learning_rate=0.05,max_depth=5,
    subsample=0.8,colsample_bytree=0.8,early_stopping_rounds=30,
    eval_metric='logloss',random_state=42,n_jobs=-1,verbosity=0)
xgb_m.fit(X_tr,y_tr,eval_set=[(X_va,y_va)],verbose=False)
xgb_tp=xgb_m.predict_proba(X_te)[:,1]; xgb_ta=accuracy_score(y_te,xgb_m.predict(X_te))

print("MODEL RESULTS ON TEST SET:")
models = {'LR':lr_tp,'RF':rf_tp,'LGBM':lgbm_tp,'XGB':xgb_tp}
accs   = {'LR':lr_ta,'RF':rf_ta,'LGBM':lgbm_ta,'XGB':xgb_ta}
for k in models:
    print(f"  {k}: Acc={accs[k]:.4f}  AUC={roc_auc_score(y_te,models[k]):.4f}")

# Feature importance
fi = pd.Series(rf.feature_importances_, index=FEAT).sort_values(ascending=False)
print("\nTop RF Feature Importances:")
print(fi.head(10).round(4))

fi_lgbm = pd.Series(lgbm.feature_importances_, index=FEAT).sort_values(ascending=False)

# ML trading backtest (RF, best model)
def ml_backtest(df_sec, probs, tl=0.58, ts=0.42):
    d = df_sec.reset_index(drop=True)
    ec,pl,tr=[],[],[]
    pos=0; ep=0.0; ei=0; eq=0.0; MH=5
    ps=np.concatenate([[0.5],probs[:-1]])
    for i in range(1,len(d)):
        op=d.loc[i,'open']; cp=d.loc[i,'close']; pb=ps[i]
        held=i-ei; bpnl=0.0
        if pos==1 and held>=MH and pb<ts:
            pnl=(cp-ep)-2*TC_PER_SIDE; bpnl+=pnl
            tr.append({'type':'long','entry':ep,'exit':cp,'pnl':pnl,'bars':held}); pos=0
        elif pos==-1 and held>=MH and pb>tl:
            pnl=(ep-cp)-2*TC_PER_SIDE; bpnl+=pnl
            tr.append({'type':'short','entry':ep,'exit':cp,'pnl':pnl,'bars':held}); pos=0
        if pos==0:
            if pb>tl: pos=1; ep=op; ei=i
            elif pb<ts: pos=-1; ep=op; ei=i
        eq+=bpnl; ec.append(eq); pl.append(bpnl)
    return np.array(ec),np.array(pl),pd.DataFrame(tr)

test_sec = df_ml.iloc[ve:].reset_index(drop=True)
ec_ml,pl_ml,tr_ml = ml_backtest(test_sec, rf_tp)

# Mean-reversion on same test period
def mean_rev_on_df(d):
    d=d.reset_index(drop=True)
    le=((d['rsi_14']<30)&(d['bb_pct']<0.1)).shift(1).fillna(False)
    se=((d['rsi_14']>70)&(d['bb_pct']>0.9)).shift(1).fillna(False)
    lx=((d['rsi_14']>50)|(d['close']>d['sma_30'])).shift(1).fillna(False)
    sx=((d['rsi_14']<50)|(d['close']<d['sma_30'])).shift(1).fillna(False)
    ec,pl,tr=[],[],[]
    pos=0; ep=0.0; ei=0; eq=0.0
    for i in range(1,len(d)):
        op=d.loc[i,'open']; cp=d.loc[i,'close']; atr=d.loc[i,'atr_14']
        atr=atr if not np.isnan(atr) else 0.1; held=i-ei; bpnl=0.0
        sp=ep-2*atr if pos==1 else ep+2*atr
        if pos==1 and op<=sp: pnl=(sp-ep)-2*TC_PER_SIDE; bpnl+=pnl; tr.append({'type':'long','pnl':pnl}); pos=0
        elif pos==-1 and op>=sp: pnl=(ep-sp)-2*TC_PER_SIDE; bpnl+=pnl; tr.append({'type':'short','pnl':pnl}); pos=0
        if pos==1 and held>=5 and lx.iloc[i]:
            pnl=(cp-ep)-2*TC_PER_SIDE; bpnl+=pnl; tr.append({'type':'long','pnl':pnl}); pos=0
        elif pos==-1 and held>=5 and sx.iloc[i]:
            pnl=(ep-cp)-2*TC_PER_SIDE; bpnl+=pnl; tr.append({'type':'short','pnl':pnl}); pos=0
        if pos==0:
            if le.iloc[i]: pos=1; ep=op; ei=i
            elif se.iloc[i]: pos=-1; ep=op; ei=i
        eq+=bpnl; ec.append(eq); pl.append(bpnl)
    return np.array(ec), np.array(pl), pd.DataFrame(tr)

test_mr_df = df_ml.iloc[ve:].reset_index(drop=True)  # use same df with indicators
ec_mr,pl_mr,tr_mr = mean_rev_on_df(test_mr_df)

def perf_summary(ec,pl,trd,lbl):
    BY=252*24*60; n=len(ec); yrs=n/BY
    tr_tot=ec[-1]; ar=tr_tot/yrs
    bm=np.nanmean(pl); bs=np.nanstd(pl)
    sh=(bm/bs)*np.sqrt(BY) if bs>0 else 0
    dn=pl[pl<0]; so=(bm/np.std(dn))*np.sqrt(BY) if len(dn)>0 else 0
    rm=np.maximum.accumulate(ec); dd=(ec-rm).min()
    wr=float((trd['pnl']>0).mean()) if len(trd) else 0
    gp=trd[trd['pnl']>0]['pnl'].sum() if len(trd) else 0
    gl=abs(trd[trd['pnl']<0]['pnl'].sum()) if len(trd) else 1
    pf=gp/gl if gl>0 else 0
    avg=float(trd['pnl'].mean()) if len(trd) else 0
    nt=len(trd)
    print(f"\n  {lbl}:")
    print(f"    Total PnL={tr_tot:.2f}  Ann={ar:.2f}  Sharpe={sh:.3f}  Sortino={so:.3f}")
    print(f"    MaxDD={dd:.2f}  WinRate={wr:.3f}  PF={pf:.3f}  AvgTrade={avg:.4f}  N={nt}")
    return dict(lbl=lbl,tot=tr_tot,ann=ar,sh=sh,so=so,dd=dd,wr=wr,pf=pf,avg=avg,n=nt)

print("\n" + "="*60 + "\nSTRATEGY PERFORMANCE ON TEST SET")
p_ml  = perf_summary(ec_ml,  pl_ml,  tr_ml,  "ML-RF")
p_mr  = perf_summary(ec_mr,  pl_mr,  tr_mr,  "Mean-Rev Rule")

# Full period mean-rev
def mean_rev_full(df_full):
    d=df_full.reset_index(drop=True)
    le=((d['rsi_14']<30)&(d['bb_pct']<0.1)).shift(1).fillna(False)
    se=((d['rsi_14']>70)&(d['bb_pct']>0.9)).shift(1).fillna(False)
    lx=((d['rsi_14']>50)|(d['close']>d['sma_30'])).shift(1).fillna(False)
    sx=((d['rsi_14']<50)|(d['close']<d['sma_30'])).shift(1).fillna(False)
    ec,pl,tr=[],[],[]
    pos=0; ep=0.0; ei=0; eq=0.0
    for i in range(1,len(d)):
        op=d.loc[i,'open']; cp=d.loc[i,'close']; atr=d.loc[i,'atr_14']
        atr=atr if not np.isnan(atr) else 0.1; held=i-ei; bpnl=0.0
        sp=ep-2*atr if pos==1 else ep+2*atr
        if pos==1 and op<=sp: pnl=(sp-ep)-2*TC_PER_SIDE; bpnl+=pnl; tr.append({'type':'long','pnl':pnl}); pos=0
        elif pos==-1 and op>=sp: pnl=(ep-sp)-2*TC_PER_SIDE; bpnl+=pnl; tr.append({'type':'short','pnl':pnl}); pos=0
        if pos==1 and held>=5 and lx.iloc[i]:
            pnl=(cp-ep)-2*TC_PER_SIDE; bpnl+=pnl; tr.append({'type':'long','pnl':pnl}); pos=0
        elif pos==-1 and held>=5 and sx.iloc[i]:
            pnl=(ep-cp)-2*TC_PER_SIDE; bpnl+=pnl; tr.append({'type':'short','pnl':pnl}); pos=0
        if pos==0:
            if le.iloc[i]: pos=1; ep=op; ei=i
            elif se.iloc[i]: pos=-1; ep=op; ei=i
        eq+=bpnl; ec.append(eq); pl.append(bpnl)
    return np.array(ec), np.array(pl), pd.DataFrame(tr)

ec_mr_full,pl_mr_full,tr_mr_full = mean_rev_full(df_ml)
p_mr_full = perf_summary(ec_mr_full,pl_mr_full,tr_mr_full,"Mean-Rev Rule (FULL)")

# ---- Figures ----
plt.style.use('seaborn-v0_8-darkgrid')

# Fig 3: equity curves
fig,axes=plt.subplots(2,2,figsize=(16,10))
fig.suptitle('Strategy Equity Curves & Drawdowns',fontsize=15,fontweight='bold')
axes[0,0].plot(ec_mr_full,color=COLORS['bull'],lw=1.2,label='Mean-Rev (full)')
axes[0,0].axhline(0,color='black',lw=0.8,ls='--')
axes[0,0].set_title('Mean-Reversion Rule – Full Period'); axes[0,0].legend()
rm=np.maximum.accumulate(ec_mr_full); dd=ec_mr_full-rm
axes[0,1].fill_between(range(len(dd)),dd,0,color=COLORS['bear'],alpha=0.5)
axes[0,1].set_title('Mean-Reversion Drawdown – Full Period')
axes[1,0].plot(ec_ml,color=COLORS['accent'],lw=1.2,label='ML-RF')
axes[1,0].plot(ec_mr,color=COLORS['bull'],lw=1.2,label='Mean-Rev')
axes[1,0].axhline(0,color='black',lw=0.8,ls='--'); axes[1,0].legend()
axes[1,0].set_title('Test Period: ML vs Mean-Reversion')
fi.head(15).plot.barh(ax=axes[1,1],color=COLORS['neutral']); axes[1,1].invert_yaxis()
axes[1,1].set_title('RF Feature Importance (Top 15)')
plt.tight_layout()
plt.savefig('/home/claude/figs/fig3_equity_curves.png',dpi=150,bbox_inches='tight'); plt.close()

# Fig 4: ML evaluation
fig,axes=plt.subplots(2,2,figsize=(16,10))
fig.suptitle('ML Model Evaluation',fontsize=15,fontweight='bold')
fi.head(15).plot.barh(ax=axes[0,0],color=COLORS['neutral']); axes[0,0].invert_yaxis()
axes[0,0].set_title('RF Feature Importance (Top 15)')
cm=confusion_matrix(y_te,rf.predict(X_te))
sns.heatmap(cm,annot=True,fmt='d',ax=axes[0,1],cmap='Blues',
            xticklabels=['Down','Up'],yticklabels=['Down','Up'])
axes[0,1].set_title('RF Confusion Matrix (Test)'); axes[0,1].set_xlabel('Predicted'); axes[0,1].set_ylabel('Actual')

from sklearn.calibration import calibration_curve
pt,pp=calibration_curve(y_te,rf_tp,n_bins=10)
axes[1,0].plot(pp,pt,'s-',color=COLORS['neutral'],label='RF')
pt2,pp2=calibration_curve(y_te,lgbm_tp,n_bins=10)
axes[1,0].plot(pp2,pt2,'s-',color=COLORS['accent'],label='LGBM')
axes[1,0].plot([0,1],[0,1],'k--',alpha=0.5,label='Perfect')
axes[1,0].set_title('Calibration Curves'); axes[1,0].legend()
# Trade PnL dist
if len(tr_ml)>0:
    axes[1,1].hist(tr_ml['pnl'].clip(-2,2),bins=50,color=COLORS['neutral'],alpha=0.7)
    axes[1,1].axvline(0,color='red',lw=1)
    axes[1,1].set_title('ML Trade PnL Distribution (clipped ±2)')
plt.tight_layout()
plt.savefig('/home/claude/figs/fig4_ml_evaluation.png',dpi=150,bbox_inches='tight'); plt.close()

# Fig 5: Seasonality
fig,axes=plt.subplots(2,2,figsize=(16,10))
fig.suptitle('EDA – Seasonality & Distributions',fontsize=15,fontweight='bold')
df['ret']=df['close'].pct_change().replace([np.inf,-np.inf],np.nan)
df['hour_c']=df['date'].dt.hour; df['dow']=df['date'].dt.dayofweek
hr=df.groupby('hour_c')['ret'].mean()*100
axes[0,0].bar(hr.index,hr.values,color=[COLORS['bull'] if v>0 else COLORS['bear'] for v in hr.values])
axes[0,0].set_title('Avg Return by Hour (UTC)'); axes[0,0].set_xlabel('Hour'); axes[0,0].axhline(0,color='black',lw=0.8)
hv=df.groupby('hour_c')['ret'].std()*100
axes[0,1].bar(hv.index,hv.values,color=COLORS['accent'])
axes[0,1].set_title('Return Volatility by Hour'); axes[0,1].set_xlabel('Hour')
dr=df.groupby('dow')['ret'].mean()*100; dl=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
axes[1,0].bar(range(len(dr)),dr.values,color=[COLORS['bull'] if v>0 else COLORS['bear'] for v in dr.values])
axes[1,0].set_xticks(range(len(dr))); axes[1,0].set_xticklabels([dl[i] for i in dr.index])
axes[1,0].set_title('Avg Return by Day of Week'); axes[1,0].axhline(0,color='black',lw=0.8)
rc=df['ret'].dropna(); rc=rc[np.abs(rc)<rc.quantile(0.999)]
axes[1,1].hist(rc,bins=200,color=COLORS['neutral'],alpha=0.7,edgecolor='none')
axes[1,1].set_title(f'Return Distribution | Skew={rc.skew():.3f} Kurt={rc.kurtosis():.0f}')
plt.tight_layout()
plt.savefig('/home/claude/figs/fig2_seasonality.png',dpi=150,bbox_inches='tight'); plt.close()

# Fig 1: Price overview  
fig,axes=plt.subplots(3,1,figsize=(16,12))
fig.suptitle('Price Overview & Volatility',fontsize=15,fontweight='bold')
axes[0].plot(df['date'],df['close'],color=COLORS['neutral'],lw=0.4,alpha=0.8)
axes[0].axhline(0,color='red',lw=0.8,ls='--',alpha=0.5); axes[0].set_title('Close Price'); axes[0].set_ylabel('Price')
rv=df['ret'].rolling(60*24).std()*np.sqrt(60*24*252)
axes[1].plot(df['date'],rv,color=COLORS['accent'],lw=0.8); axes[1].set_title('Rolling 24h Ann. Volatility')
axes[2].hist(rc,bins=200,color=COLORS['neutral'],alpha=0.7,edgecolor='none')
axes[2].set_title('1-min Return Distribution'); axes[2].set_xlabel('Return')
plt.tight_layout(); plt.savefig('/home/claude/figs/fig1_price_overview.png',dpi=150,bbox_inches='tight'); plt.close()

print("\nAll figures saved.")
print(f"\nModel accuracy: LR={lr_ta:.4f}  RF={rf_ta:.4f}  LGBM={lgbm_ta:.4f}  XGB={xgb_ta:.4f}")
print(f"Model AUC:      LR={roc_auc_score(y_te,lr_tp):.4f}  RF={roc_auc_score(y_te,rf_tp):.4f}  LGBM={roc_auc_score(y_te,lgbm_tp):.4f}  XGB={roc_auc_score(y_te,xgb_tp):.4f}")