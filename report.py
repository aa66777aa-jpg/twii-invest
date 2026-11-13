"""日報 / 週報 / 月報：更新資料、計算指標並產生報告。

用法：python3 report.py [daily|weekly|monthly] [--no-update]（預設 weekly）
各類報告只保留最新一份（舊檔在存新檔時刪除，歷史可從 git 查）。
- daily   → reports/daily/YYYY-MM-DD.md   今天是不是本月相對低價的買點（不改倍數）
- weekly  → reports/weekly/YYYY-MM-DD.md  本月建議倍數、觸發點、歷史類似情況
- monthly → reports/monthly/YYYY-MM.md    本月正式倍數（第一週判斷）、上月回顧
"""
import sys
from pathlib import Path

import pandas as pd

from twii import analysis, config, data, indicators, strategy

REPORT_DIR = Path(__file__).parent / "reports"
FOOTER = "> 以 0050 / 006208 等追蹤大盤 ETF 執行。僅供參考，非投資建議。"


def _save(kind, name, lines):
    text = "\n".join(lines)
    print(text)
    out = REPORT_DIR / kind / f"{name}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    for old in out.parent.glob("*.md"):  # 只保留最新一份
        if old != out:
            old.unlink()
    out.write_text(text + "\n", encoding="utf-8")
    print(f"\n已存檔：{out}")


def _hist_lines(hist):
    """近 12 個月倍數表格與累計多投 / 少投份數。"""
    extra = sum(m - 1 for _, m in hist)
    streak = 0
    for _, m in reversed(hist):
        if m <= 1:
            break
        streak += 1
    return [
        "| " + " | ".join(f"{p.month}月" for p, _ in hist) + " |",
        "|" + "---|" * len(hist),
        "| " + " | ".join(f"{m:g}x" for _, m in hist) + " |",
        "",
        (f"比正常定期定額**多投 {extra:g} 份**（1x = 1 份），需要額外準備這麼多資金"
         if extra > 0 else
         f"比正常定期定額**少投 {-extra:g} 份**（1x = 1 份），過熱減碼省下的錢可留給加碼"
         if extra < 0 else "與正常定期定額持平")
        + (f"；目前已連續加碼 {streak} 個月。" if streak else "。"),
    ]


def daily(get):
    ddf = indicators.add_all(get("D"))
    wdf = indicators.add_all(get("W"))

    now = pd.Timestamp.now(tz="Asia/Taipei").tz_localize(None)
    row, prev = ddf.iloc[-1], ddf.iloc[-2]
    day = row.name
    intraday = day.date() == now.date() and now.time() < pd.Timestamp("13:30").time()
    chg = row["close"] / prev["close"] - 1

    mult, _ = strategy.multiplier(wdf.iloc[-1], wdf.iloc[-2])
    signals, base, base_label = analysis.buy_signals(ddf, day)
    low_n = ddf["close"].iloc[-config.DAILY_LOW_DAYS:].min()
    days_left = len(pd.bdate_range(day + pd.Timedelta(days=1), day + pd.offsets.MonthEnd(0)))

    if signals:
        verdict = "今天相對低價，可以買進本月份額"
        if mult > 1:
            verdict += "（加碼月建議分次買，今天先買一部分）"
    elif days_left <= config.MONTH_END_BUY_DAYS:
        verdict = f"本月只剩約 {days_left} 個交易日，還沒買的話就照常買進，不要再等"
    else:
        verdict = (f"今天沒有明顯低價，可以再觀察；本月還剩約 {days_left} 個交易日，"
                   f"最後 {config.MONTH_END_BUY_DAYS} 個交易日還沒遇到低價就照常買進")

    recent = ddf.iloc[-config.DAILY_RECENT_ROWS:]
    pct = ddf["close"].pct_change()
    lines = [
        f"# 加權指數 TWII 日報 ({day.date()}{'，盤中' if intraday else ''})",
        "",
        f"- 收盤：**{row['close']:,.2f}**（{chg:+.2%}）",
        f"- {base_label} {base:,.0f}，今天 {row['close'] / base - 1:+.1%}；"
        f"近 {config.DAILY_LOW_DAYS} 日最低收盤 {low_n:,.0f}",
        "",
        f"## 本月倍數：{mult:g}x（週線規則，詳見週報）",
        "",
        f"## 今天：{verdict}",
        *[f"- {s}" for s in signals],
        "",
        "## 最近交易日",
        "| 日期 | 收盤 | 漲跌 | 日K |",
        "|---|---|---|---|",
        *[f"| {ts.date()} | {r['close']:,.0f} | {pct[ts]:+.2%} | {r['k']:.0f} |"
          for ts, r in recent.iterrows()],
        "",
        FOOTER,
    ]
    _save("daily", day.date(), lines)


def weekly(get):
    df = indicators.add_all(get("W"))
    row, prev = df.iloc[-1], df.iloc[-2]
    mult, reasons = strategy.multiplier(row, prev)
    action, pros, cons = strategy.assess(row, prev, mult)

    chg = row["close"] / prev["close"] - 1
    cond, stats, episodes = analysis.similar_history(df)
    stat_lines = ["| 期間 | 樣本週數 | 上漲機率 | 中位數 | 最差 | 最好 |", "|---|---|---|---|---|---|"]
    for _, s in stats.iterrows():
        stat_lines.append(f"| {s['期間']} | {s['樣本週數']} | {s['上漲機率']:.0%} | "
                          f"{s['中位數']:+.1%} | {s['最差']:+.1%} | {s['最好']:+.1%} |")

    today = pd.Timestamp.now(tz="Asia/Taipei").date()  # 雲端機器是 UTC，固定用台北時間
    lines = [
        f"# 加權指數 TWII 週報 ({today})",
        "",
        f"- 本週收盤：**{row['close']:,.2f}**（{chg:+.2%}），週K日期 {row.name.date()}",
        f"- 52週高點：{row['high_52w']:,.2f}，回檔 {row['drawdown']:.1%}",
        f"- 均線：13週 {row['ma13']:,.0f} / 26週 {row['ma26']:,.0f} / 52週 {row['ma52']:,.0f}",
        f"- Stoch(14,1,3)：K {row['k']:.2f} / D {row['d']:.2f}",
        f"- MACD(12,26,9)：DIF {row['macd']:.2f} / Signal {row['macd_signal']:.2f} / Hist {row['macd_hist']:.2f}",
        "",
        f"## 本月建議投入：{mult:g}x",
        *[f"- {r}" for r in reasons],
        "",
        f"## 目前建議：{action}",
        "**偏多因素**",
        *[f"- {x}" for x in pros or ["無"]],
        "",
        "**風險提醒**",
        *[f"- {x}" for x in cons or ["無"]],
        "",
        "## 距離下一個觸發點",
        *[f"- {x}" for x in analysis.triggers(df)],
        "",
        "## 歷史類似情況",
        f"條件：{cond}（2000 年以來，約 {episodes} 段獨立行情）",
        "",
        *(stat_lines if not stats.empty else ["樣本不足"]),
        "",
        "> 同一段行情的連續週會重複計入樣本週數，實際獨立事件以「段」數為準。",
        "",
        "> 月線大方向、近 12 個月倍數紀錄見月報。" + FOOTER[2:],
    ]
    _save("weekly", today, lines)


def monthly(get):
    df = indicators.add_all(get("W"))
    mdf = indicators.add_all(get("M"))
    ddf = indicators.add_all(get("D"))

    hist = analysis.multiplier_history(df)  # 本月以第一週判斷（正式規則）
    cur = hist[-1][0]
    first = df[df.index.to_period("M") == cur].index[0]
    i = df.index.get_loc(first)
    mult, reasons = strategy.multiplier(df.iloc[i], df.iloc[i - 1])
    latest, _ = strategy.multiplier(df.iloc[-1], df.iloc[-2])
    month_text, _ = analysis.monthly_trend(mdf)

    # 上月回顧
    pm = cur - 1
    m_idx = mdf.index.to_period("M")
    review = []
    if (m_idx == pm).any() and (m_idx == pm - 1).any():
        pr = mdf[m_idx == pm].iloc[0]
        pchg = pr["close"] / mdf[m_idx == pm - 1].iloc[0]["close"] - 1
        pdays = ddf[ddf.index.to_period("M") == pm]
        low_day = pdays["close"].idxmin()
        review += [
            f"- 收盤 {pr['close']:,.0f}（{pchg:+.1%}），月內高 {pr['high']:,.0f} / 低 {pr['low']:,.0f}；"
            f"最低收盤 {pdays['close'].min():,.0f}（{low_day.date()}）",
        ]
        sig_rows = [(ts, analysis.signal_values(ddf, ts)[:3]) for ts in pdays.index]
        sig_rows = [(ts, v) for ts, v in sig_rows if analysis.is_signal(*v)]
        if sig_rows:
            review += ["", f"上月出現相對低價訊號的日子（日K < {config.KD_OVERSOLD}、"
                       f"收盤創近 {config.DAILY_LOW_DAYS} 日新低、比月初低 "
                       f"{config.DAILY_DIP_FROM_MONTH:.0%} 以上，任一成立）：", "",
                       f"| 日期 | 收盤 | 日K | 比月初 | {config.DAILY_LOW_DAYS} 日新低 |",
                       "|---|---|---|---|---|"]
            review += [f"| {ts.date()} | {ddf.loc[ts, 'close']:,.0f} | {k:.0f} | {vs:+.1%} | "
                       f"{'✓' if low else ''} |" for ts, (k, vs, low) in sig_rows]
        else:
            review.append("- 上月沒有出現相對低價訊號（月底照常買進）")
    else:
        review.append("- 資料不足")

    lines = [
        f"# 加權指數 TWII 月報 ({cur.year}-{cur.month:02d})",
        "",
        f"## 本月投入倍數：{mult:g}x（以 {first.date()} 當週判斷）",
        *[f"- {r}" for r in reasons],
        *([f"- 最新一週規則為 {latest:g}x，與月初不同；以週報為準"] if latest != mult else []),
        "",
        f"## 上月回顧（{pm.year}-{pm.month:02d}）",
        *review,
        "",
        "## 月線大方向",
        f"- {month_text}",
        "",
        "## 近 12 個月倍數紀錄",
        *_hist_lines(hist),
        "",
        "> 距離下一個觸發點見週報。" + FOOTER[2:],
    ]
    _save("monthly", f"{cur.year}-{cur.month:02d}", lines)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kind = args[0] if args else "weekly"
    run = {"daily": daily, "weekly": weekly, "monthly": monthly}.get(kind)
    if run is None:
        sys.exit("用法：python3 report.py [daily|weekly|monthly] [--no-update]")
    get = data.load if "--no-update" in sys.argv else (lambda r: data.update(r)[0])
    run(get)


if __name__ == "__main__":
    main()
