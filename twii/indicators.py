"""技術指標：計算方式對齊鉅亨 / TradingView 圖表。"""
import pandas as pd

from . import config


def stoch(df, k=config.STOCH_K, smooth=config.STOCH_SMOOTH, d=config.STOCH_D):
    low_n = df["low"].rolling(k).min()
    high_n = df["high"].rolling(k).max()
    raw = 100 * (df["close"] - low_n) / (high_n - low_n)
    k_line = raw.rolling(smooth).mean()
    d_line = k_line.rolling(d).mean()
    return k_line, d_line


def macd(close, fast=config.MACD_FAST, slow=config.MACD_SLOW, signal=config.MACD_SIGNAL):
    dif = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = dif.ewm(span=signal, adjust=False).mean()
    return dif, sig, dif - sig


def add_all(df):
    out = df.copy()
    out["k"], out["d"] = stoch(out)
    out["macd"], out["macd_signal"], out["macd_hist"] = macd(out["close"])
    for w in config.MA_WEEKS:
        out[f"ma{w}"] = out["close"].rolling(w).mean()
    out["high_52w"] = out["high"].rolling(52, min_periods=1).max()
    out["drawdown"] = 1 - out["close"] / out["high_52w"]
    return out
