"""回測：加碼規則 vs. 純定期定額，含公平比較與規則拆解。

用法：python3 backtest.py [起始年份，預設 2010]

以「份」計：1x = 每月 1 份，每月第一週收盤買入。報酬率、IRR 與每份金額無關。
三種比較方式：
- 無上限：需要多少就投多少（規則總投入較多，只看報酬率不完全公平）。
- IRR：考慮每筆錢投入的時間，加碼的錢多投在後期，持有較短，報酬率會被高估或低估。
- 現金池：每月固定存入 1 份到現金池（與純定期定額相同的錢），依倍數從池中投入，
  池子不夠就投剩下的；期末市值 + 剩餘現金（現金不計息）。這是最公平的比較。
注意：加權指數為價格指數（不含股息），實際 ETF 報酬會再高一些。
"""
import sys

import pandas as pd

from twii import config, data, indicators, strategy


def _irr(flows, final_value):
    """月現金流（每月投入的份數）與期末市值 → 年化 IRR（二分法）。"""
    n = len(flows)

    def npv(r):
        return sum(-f * (1 + r) ** (n - i) for i, f in enumerate(flows)) + final_value

    lo, hi = -0.99, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (1 + lo) ** 12 - 1


def _months(df, start_year):
    """每月第一週的 (row, prev)。"""
    sub = df[df.index.year >= start_year]
    out = []
    for ts in sub.groupby(sub.index.to_period("M")).head(1).index:
        i = df.index.get_loc(ts)
        out.append((df.iloc[i], df.iloc[i - 1] if i > 0 else None))
    return out


def simulate(months, last_close, **rule):
    """單一規則的完整結果。rule 為 strategy.multiplier 的參數；None 代表純定期定額 1x。"""
    mults = [1.0 if rule.get("plain") else
             strategy.multiplier(r, p, **{k: v for k, v in rule.items() if k != "plain"})[0]
             for r, p in months]
    prices = [r["close"] for r, _ in months]
    n = len(months)

    cost = sum(mults)
    units = sum(m / px for m, px in zip(mults, prices))
    value = units * last_close

    # 備用資金需求：累計多投 Σ(m-1) 的最高點；以及「把減碼省下的錢留著」時單一波段最多要補多少
    cum, peak, trough, max_wave = 0.0, 0.0, 0.0, 0.0
    peak_month = None
    for (r, _), m in zip(months, mults):
        cum += m - 1
        if cum > peak:
            peak, peak_month = cum, r.name
        trough = min(trough, cum)
        max_wave = max(max_wave, cum - trough)

    # 現金池：每月存入 1 份，依倍數投入，不夠就投剩下的
    cash, pool_units = 0.0, 0.0
    for m, px in zip(mults, prices):
        cash += 1.0
        buy = min(m, cash)
        cash -= buy
        pool_units += buy / px
    pool_value = pool_units * last_close + cash

    return {
        "投入": cost,
        "報酬": value / cost - 1,
        "平均成本": cost / units,
        "IRR": _irr(mults, value),
        "累計多投高點": peak,
        "高點月份": peak_month.strftime("%Y-%m") if peak_month is not None else "-",
        "單波段需備用": max_wave,
        "現金池終值": pool_value,
        "現金池剩餘": cash,
        "_n": n,
    }


VARIANTS = [
    ("純定期定額 1x", {"plain": True}),
    ("目前規則（全部）", {}),
    ("只有回檔分級", {"kd_bonus": False, "overheat": False}),
    ("回檔 + KD 加碼", {"overheat": False}),
    ("回檔 + 過熱減碼", {"kd_bonus": False}),
]

SENSITIVITY = [
    ("回檔級距 8/16/24%", {"tiers": [(0.24, 3.0), (0.16, 2.0), (0.08, 1.5)]}),
    ("回檔級距 12/24/36%", {"tiers": [(0.36, 3.0), (0.24, 2.0), (0.12, 1.5)]}),
    ("過熱門檻 高於年線 15%", {"overheat_above": 0.15}),
    ("過熱門檻 高於年線 25%", {"overheat_above": 0.25}),
    ("過熱門檻 高於年線 30%", {"overheat_above": 0.30}),
]


def _table(title, rows, base_pool):
    print(f"\n## {title}")
    print("| 規則 | 投入份 | 報酬 | 平均成本 | IRR | 現金池終值 | vs 純定期定額 | 累計多投高點 | 單波段需備用 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, r in rows:
        print(f"| {name} | {r['投入']:.1f} | {r['報酬']:+.1%} | {r['平均成本']:,.0f} | {r['IRR']:.2%} | "
              f"{r['現金池終值']:.1f} | {r['現金池終值'] / base_pool - 1:+.1%} | "
              f"{r['累計多投高點']:.1f}（{r['高點月份']}） | {r['單波段需備用']:.1f} |")


def run(start_year=2010):
    df = indicators.add_all(data.load("W"))
    months = _months(df, start_year)
    last = df["close"].iloc[-1]
    print(f"# 回測 {months[0][0].name.date()} ~ {df.index[-1].date()}，共 {len(months)} 個月")
    print("（現金池：每月存 1 份，總共存入的錢與純定期定額相同）")

    results = [(name, simulate(months, last, **rule)) for name, rule in VARIANTS]
    base_pool = results[0][1]["現金池終值"]
    _table("規則拆解", results, base_pool)
    _table("參數敏感度（其餘規則不變）",
           [(name, simulate(months, last, **rule)) for name, rule in SENSITIVITY], base_pool)


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 2010)
