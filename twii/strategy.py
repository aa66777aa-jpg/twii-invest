"""中長期加碼規則：依回檔幅度、週 KD、過熱程度決定本期投入倍數。"""
import pandas as pd

from . import config


def multiplier(row, prev, tiers=None, kd_bonus=True, overheat=True, overheat_above=None):
    """回傳 (倍數, 理由清單)。row/prev 為加上指標後的週資料列。

    其餘參數供回測做規則拆解 / 敏感度測試，預設即 config 的規則。
    """
    tiers = config.DRAWDOWN_TIERS if tiers is None else tiers
    overheat_above = config.OVERHEAT_ABOVE_MA52 if overheat_above is None else overheat_above
    reasons = []
    m = 1.0
    for dd, mult in tiers:
        if row["drawdown"] >= dd:
            m = mult
            reasons.append(f"距52週高點回檔 {row['drawdown']:.1%} ≥ {dd:.0%} → {mult}x")
            break

    golden = prev is not None and prev["k"] <= prev["d"] and row["k"] > row["d"]
    if kd_bonus and golden and min(row["k"], prev["k"]) < config.KD_OVERSOLD:
        m += 0.5
        reasons.append("週KD低檔黃金交叉 → +0.5x")

    heat = (row["close"] / row["ma52"] - 1) if pd.notna(row["ma52"]) else 0
    if overheat and m == 1.0 and row["k"] > config.KD_OVERBOUGHT and heat > overheat_above:
        m = 0.5
        reasons.append(f"高於年線 {heat:.1%} 且週K>{config.KD_OVERBOUGHT} 過熱 → 0.5x")

    if not reasons:
        reasons.append("無特殊訊號 → 正常定期定額 1x")
    return m, reasons


def assess(row, prev, mult):
    """依目前狀況給出操作建議：(結論, 偏多理由, 風險提醒)。

    回檔幅度與低檔黃金交叉已列在倍數理由，這裡不重複。
    """
    pros, cons = [], []
    golden = row["k"] > row["d"] and prev["k"] <= prev["d"]
    if golden and min(row["k"], prev["k"]) >= config.KD_OVERSOLD:
        pros.append(f"週 KD 黃金交叉（K {row['k']:.0f}），短線動能翻多")
    elif not golden and row["k"] < config.KD_OVERSOLD:
        pros.append(f"週 K {row['k']:.0f} 位於超賣區")
    if row["close"] > row["ma13"] > row["ma26"] > row["ma52"]:
        pros.append("均線多頭排列，長期多頭結構完整")
    elif row["close"] > row["ma52"]:
        pros.append("仍在 52 週均線之上，長期多頭結構未破")
    else:
        cons.append("已跌破 52 週均線，長期趨勢轉弱，可能有更深回檔")

    if row["macd_hist"] < 0:
        worse = row["macd_hist"] < prev["macd_hist"]
        cons.append("週 MACD 柱狀體為負" + ("且持續擴大" if worse else "但開始收斂")
                    + "，中期趨勢仍在修正")
    if row["close"] < row["ma26"]:
        cons.append(f"收盤低於 26 週均線 {row['ma26']:,.0f}，上方有壓力")
    if row["k"] > config.KD_OVERBOUGHT:
        cons.append(f"週 K {row['k']:.0f} 位於過熱區")

    if mult >= 2.5:
        action = "積極加碼"
    elif mult > 1:
        action = "適度加碼"
    elif mult == 1:
        action = "維持定期定額"
    else:
        action = "減碼、保留資金"
    if mult > 1 and len(cons) >= 2:
        action += "，但趨勢未轉強，建議分次買進、不要一次重壓"
    return action, pros, cons
