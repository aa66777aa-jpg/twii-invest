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

以上都是本機執行的指令，報告完全由程式依規則產生，不需要 AI 或 API key。每類報告只保留最新一份。

### 自動執行（GitHub Actions）

Repo：<https://github.com/aa66777aa-jpg/twii-invest>。週一到週五 14:30（台北時間）自動跑日報，週五加跑週報、每月 1–7 日加跑月報，並把結果 commit 回 repo。雲端用 Python 3.12（Ubuntu 已無 3.9），程式仍須相容 3.9。

```bash
git pull                       # 取得最新的自動報告
gh workflow run report         # 手動觸發（或 GitHub 網頁 Actions → report → Run workflow）
gh workflow run report -f kind=weekly   # 指定報告：daily / weekly / monthly / all
```

本機跑的報告只供自己看，不要 commit／上傳 `reports/` 和 `data/`，以免覆蓋自動產生的報告；用 git 時可用 `git checkout reports/` 還原。

用 GitHub 網頁拖曳上傳時，`.github/`、`.gitignore` 等以 `.` 開頭的檔案會被略過，改這些檔要用 git push 或網頁「Create new file」。

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
