# TWII 中長期投資工具

台股加權指數每月定期定額，依回檔幅度與週 KD 調整投入倍數，只買不賣；並有日報幫忙在月內挑相對低價的日子買進。規則在 [twii/config.py](twii/config.py)，變更歷程見 [CHANGELOG.md](CHANGELOG.md)。

```bash
pip3 install -r requirements.txt
python3 report.py daily        # 日報：今天是否為本月相對低價的買點 → reports/daily/YYYY-MM-DD.md
python3 report.py weekly       # 週報（不加參數也是週報）→ reports/weekly/YYYY-MM-DD.md
python3 report.py monthly      # 月報：本月正式倍數、上月回顧 → reports/monthly/YYYY-MM.md
python3 report.py weekly --no-update  # 使用快取資料，三種報告都適用
python3 backtest.py 2010       # 回測：純定期定額 vs 加碼規則
```

每類報告只保留最新一份。GitHub Actions 會在週一到週五 14:30（台北時間）自動跑日報，週五加跑週報、每月 1–7 日加跑月報，並把結果 commit 回 repo，本機 `git pull` 就能看。手動觸發：GitHub 的 Actions → report → Run workflow。

```text
twii-invest/
├── CLAUDE.md / AGENTS.md / SPEC.md / README.md
├── CHANGELOG.md        # 規則與決策變更紀錄
├── report.py           # 日報 / 週報 / 月報產生
├── backtest.py         # 回測與參數敏感度
├── requirements.txt
├── .github/workflows/  # report.yml：每日自動產生報告
├── twii/               # config（規則參數）、data、indicators、strategy、analysis
├── data/               # 日線、週線、月線快取 CSV（不進 git）
└── reports/            # daily/ 日報、weekly/ 週報、monthly/ 月報
```

> 加權指數不含股息，ETF 實際報酬較高。僅供個人研究，非投資建議。
