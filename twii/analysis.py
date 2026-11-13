"""報告用的輔助分析：月線大方向、歷史類似情況、距離下一個觸發點。"""
import pandas as pd

from . import config


def monthly_trend(mdf):
    """mdf 為加上指標的月線資料。回傳 (說明文字, 是否多頭)。"""
    row, prev = mdf.iloc[-1], mdf.iloc[-2]
    above_zero = row["macd"] > 0
    hist_dir = "擴大" if abs(row["macd_hist"]) > abs(prev["macd_hist"]) else "收斂"
    hist_sign = "+" if row["macd_hist"] >= 0 else "-"
    kd_dir = "K > D" if row["k"] > row["d"] else "K < D"
    if above_zero and row["macd_hist"] >= 0 and hist_dir == "擴大":
        verdict, bull = "長期多頭且動能增強，回檔偏向修正、可放心加碼", True
    elif above_zero and row["macd_hist"] >= 0:
        verdict, bull = "長期多頭，但月線動能放緩，加碼可照規則、不必超額", True
    elif above_zero:
        verdict, bull = "長期仍屬多頭（DIF 在零軸上），但月線動能轉弱，加碼宜分批", True
    else:
        verdict, bull = "長期轉空（DIF 跌破零軸），加碼保守、保留子彈", False
    text = (f"月 KD：K {row['k']:.1f} / D {row['d']:.1f}（{kd_dir}）；"
            f"月 MACD：DIF {row['macd']:,.0f}，柱狀體 {hist_sign} 且{hist_dir} → {verdict}")
    return text, bull


def _drawdown_bucket(dd):
    """回檔幅度落在哪一個區間，回傳 (下限, 上限)。"""
    edges = sorted([0.0] + [t for t, _ in config.DRAWDOWN_TIERS] + [1.0])
    for lo, hi in zip(edges, edges[1:]):
        if lo <= dd < hi:
            return lo, hi
    return edges[-2], edges[-1]


def similar_history(df):
    """找出與最新一週條件相近的歷史週，統計之後的報酬。

    條件：回檔幅度在同一區間、與 52 週均線同一側、週 KD 方向相同（K>D 或 K<D）。
    回傳 (條件說明, 統計 DataFrame, 獨立事件數)。
    """
    row = df.iloc[-1]
    lo, hi = _drawdown_bucket(row["drawdown"])
    above = row["close"] > row["ma52"]
    k_up = row["k"] > row["d"]

    hist = df.iloc[:-1].dropna(subset=["ma52", "k", "d"])
    mask = ((hist["drawdown"] >= lo) & (hist["drawdown"] < hi)
            & ((hist["close"] > hist["ma52"]) == above)
            & ((hist["k"] > hist["d"]) == k_up))
    matches = hist.index[mask]

    # 連續或相隔很近的週視為同一段行情，避免重複計算
    episodes = 0
    last_pos = None
    for ts in matches:
        pos = df.index.get_loc(ts)
        if last_pos is None or pos - last_pos > config.EPISODE_GAP_WEEKS:
            episodes += 1
        last_pos = pos

    rows = []
    for weeks in config.FORWARD_WEEKS:
        fwd = (df["close"].shift(-weeks) / df["close"] - 1).reindex(matches).dropna()
        if fwd.empty:
            continue
        rows.append({
            "期間": f"{weeks} 週後",
            "樣本週數": len(fwd),
            "上漲機率": (fwd > 0).mean(),
            "中位數": fwd.median(),
            "最差": fwd.min(),
            "最好": fwd.max(),
        })
    cond = (f"回檔 {lo:.0%}～{hi:.0%}、{'52 週均線之上' if above else '52 週均線之下'}、"
            f"週 KD {'K > D' if k_up else 'K < D'}")
    return cond, pd.DataFrame(rows), episodes


def triggers(df):
    """距離下一個倍數觸發點的價位。回傳說明文字清單。"""
    row = df.iloc[-1]
    close, high = row["close"], row["high_52w"]
    out = []

    # 1) 回檔分級價位
    for dd, mult in sorted(config.DRAWDOWN_TIERS):
        price = high * (1 - dd)
        if close > price:
            out.append(f"跌到 **{price:,.0f}**（再跌 {1 - price / close:.1%}）→ 回檔 {dd:.0%}，基本倍數 {mult}x")

    # 52 週高點何時滾出計算範圍（滾出後回檔幅度會突然變小）
    window = df["high"].iloc[-52:]
    high_date = window.idxmax()
    weeks_ago = len(window) - 1 - window.index.get_loc(high_date)
    out.append(f"52 週高點出現在 {high_date.date()}（{weeks_ago} 週前），"
               f"約 {52 - weeks_ago} 週後滾出計算範圍")

    # 2) 週 KD 超賣 / 過熱價位：以「下週」的 14 週區間（最近 13 週 + 下週）估算，
    #    假設下週的高低點不超出最近 13 週的範圍
    last13 = df.iloc[-(config.STOCH_K - 1):]
    lo13, hi13 = last13["low"].min(), last13["high"].max()
    oversold = lo13 + (hi13 - lo13) * config.KD_OVERSOLD / 100
    overbought = lo13 + (hi13 - lo13) * config.KD_OVERBOUGHT / 100
    if close > oversold:
        out.append(f"下週收在 **{oversold:,.0f}** 以下（再跌 {1 - oversold / close:.1%}）"
                   f"→ 週 K 約 < {config.KD_OVERSOLD}，進入超賣區（之後若黃金交叉再 +0.5x）")

    # 3) 過熱減碼：高於年線 X% 且週 K > 80
    #    過熱只在沒有回檔加碼時才生效，所以也要回檔小於最小級距
    min_dd = min(t for t, _ in config.DRAWDOWN_TIERS)
    heat_price = max(row["ma52"] * (1 + config.OVERHEAT_ABOVE_MA52), overbought,
                     high * (1 - min_dd))
    out.append(f"漲到 **{heat_price:,.0f}** 以上（再漲 {heat_price / close - 1:.1%}）"
               f"→ 高於年線 {config.OVERHEAT_ABOVE_MA52:.0%}、週 K > {config.KD_OVERBOUGHT}、"
               f"回檔 < {min_dd:.0%}，過熱降為 0.5x")
    return out


def multiplier_history(df, months=12):
    """近 N 個月（含本月）每月的投入倍數，以每月第一週判斷，與回測一致。

    回傳 [(月份, 倍數), ...] 由舊到新。
    """
    from . import strategy

    first_weeks = df.groupby(df.index.to_period("M")).head(1).iloc[-months:]
    out = []
    for ts in first_weeks.index:
        i = df.index.get_loc(ts)
        prev = df.iloc[i - 1] if i > 0 else None
        mult, _ = strategy.multiplier(df.iloc[i], prev)
        out.append((ts.to_period("M"), mult))
    return out


def signal_values(ddf, ts):
    """日線在 ts 這天的低價訊號數值。ddf 為加上指標的日線。

    回傳 (日K, 相對基準漲跌, 是否創近 N 日新低, 基準收盤, 基準說明)；
    基準為本月第一個交易日收盤，當天就是本月第一個交易日時改用上月最後收盤。
    """
    i = ddf.index.get_loc(ts)
    row = ddf.iloc[i]
    month = ddf.iloc[:i + 1]
    month = month[month.index.to_period("M") == ts.to_period("M")]
    if len(month) > 1:
        base, label = month["close"].iloc[0], "本月第一個交易日收盤"
    else:
        base, label = ddf["close"].iloc[i - 1], "上月最後收盤"
    vs_base = row["close"] / base - 1
    low_n = ddf["close"].iloc[max(0, i + 1 - config.DAILY_LOW_DAYS):i + 1].min()
    return row["k"], vs_base, row["close"] <= low_n, base, label


def is_signal(k, vs_base, new_low):
    return (k < config.KD_OVERSOLD or new_low
            or vs_base <= -config.DAILY_DIP_FROM_MONTH)


def buy_signals(ddf, ts):
    """日線在 ts 這天是否為本月相對低價。回傳 (訊號清單, 基準收盤, 基準說明)。"""
    k, vs_base, new_low, base, label = signal_values(ddf, ts)
    signals = []
    if k < config.KD_OVERSOLD:
        signals.append(f"日 K {k:.0f} < {config.KD_OVERSOLD}，短線超賣")
    if new_low:
        signals.append(f"收盤創近 {config.DAILY_LOW_DAYS} 個交易日新低")
    if vs_base <= -config.DAILY_DIP_FROM_MONTH:
        signals.append(f"比{label}低 {-vs_base:.1%}")
    return signals, base, label
