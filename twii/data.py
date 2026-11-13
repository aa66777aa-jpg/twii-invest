"""從鉅亨網抓取加權指數 K 線，並快取成 CSV。"""
import time
from pathlib import Path

import pandas as pd
import requests

from . import config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _fetch_chunk(resolution, newest_ts, oldest_ts):
    # 注意：鉅亨 API 的 from 是「較新」時間、to 是「較舊」時間，回傳由新到舊
    params = {
        "symbol": config.SYMBOL,
        "resolution": resolution,
        "from": newest_ts,
        "to": oldest_ts,
    }
    # 鉅亨偶爾回 502 等暫時性錯誤，重試幾次再放棄
    for attempt in range(config.API_RETRIES + 1):
        try:
            r = requests.get(config.API_URL, params=params, timeout=30,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code < 500:
                break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == config.API_RETRIES:
                raise
        if attempt < config.API_RETRIES:
            time.sleep(config.API_RETRY_WAIT * (attempt + 1))
    r.raise_for_status()
    d = r.json()["data"]
    if d.get("s") != "ok" or not d.get("t"):
        return pd.DataFrame()
    return pd.DataFrame({
        "date": pd.to_datetime(d["t"], unit="s", utc=True)
                  .tz_convert("Asia/Taipei").tz_localize(None).normalize(),
        "open": d["o"], "high": d["h"], "low": d["l"],
        "close": d["c"], "volume": d["v"],
    })


def fetch(resolution="W", start=config.HISTORY_START):
    """分段往回抓取（API 每次最多約 5 年），回傳由舊到新的 DataFrame。"""
    oldest = int(pd.Timestamp(start).timestamp())
    newest = int(time.time())
    parts = []
    while newest > oldest:
        chunk = _fetch_chunk(resolution, newest, oldest)
        if chunk.empty:
            break
        parts.append(chunk)
        earliest = int(chunk["date"].min().timestamp())
        if earliest >= newest:
            break
        newest = earliest - 1
        time.sleep(0.3)
    if not parts:
        raise RuntimeError("鉅亨 API 沒有回傳資料")
    df = (pd.concat(parts).drop_duplicates("date")
            .sort_values("date").set_index("date"))
    return df


def update(resolution="W"):
    df = fetch(resolution)
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"twii_{resolution.lower()}.csv"
    df.to_csv(path)
    return df, path


def load(resolution="W"):
    path = DATA_DIR / f"twii_{resolution.lower()}.csv"
    if not path.exists():
        return update(resolution)[0]
    return pd.read_csv(path, parse_dates=["date"], index_col="date")
