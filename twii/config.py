"""專案參數：指標設定與中長期加碼規則都集中在這裡調整。"""

# 資料來源：鉅亨網 (與 invest.cnyes.com/index/TWS/TSE01 圖表同源)
SYMBOL = "TWS:TSE01:INDEX"
API_URL = "https://ws.api.cnyes.com/ws/api/v1/charting/history"
HISTORY_START = "2000-01-01"
API_RETRIES = 3        # 暫時性錯誤（5xx / 逾時）重試次數
API_RETRY_WAIT = 10    # 每次重試等待秒數（遞增）

# 技術指標（與鉅亨圖表一致：週線 Stoch 14 1 3、MACD 12 26 9）
STOCH_K, STOCH_SMOOTH, STOCH_D = 14, 1, 3
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
MA_WEEKS = (13, 26, 52)  # 約季線、半年線、年線

# 投資規則（中長期：只買不賣，用倍數調整每月投入）
# 1x = 每月正常定期定額的金額，實際金額由使用者自訂

# 距 52 週高點的回檔幅度 → 投入倍數（由大到小判斷）
DRAWDOWN_TIERS = [
    (0.30, 3.0),
    (0.20, 2.0),
    (0.10, 1.5),
]
KD_OVERSOLD = 20       # 週 K < 20 且黃金交叉 → 額外 +0.5 倍
KD_OVERBOUGHT = 80
OVERHEAT_ABOVE_MA52 = 0.20  # 高於年線 20% 且週 K > 80 → 降為 0.5 倍

# 日報（report.py daily）：只用來挑本月哪一天買，不影響倍數
DAILY_LOW_DAYS = 20        # 收盤創近 20 個交易日（約一個月）新低 → 相對低價
DAILY_DIP_FROM_MONTH = 0.03  # 比本月第一個交易日收盤低 3% 以上 → 相對低價
DAILY_RECENT_ROWS = 5      # 報告列出最近幾個交易日
MONTH_END_BUY_DAYS = 3     # 本月剩這幾個交易日還沒買 → 不再等，照常買進

# 報告：歷史類似情況統計
FORWARD_WEEKS = (13, 26, 52)  # 統計之後 3 / 6 / 12 個月的報酬
EPISODE_GAP_WEEKS = 8         # 相隔超過 8 週才算另一段獨立行情
