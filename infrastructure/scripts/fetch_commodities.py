"""
日次コモディティ価格取得
------------------------
yfinance で過去2年の日足を取得し、data/commodities/daily-prices.json に保存する。
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "commodities"
OUT_FILE = OUT_DIR / "daily-prices.json"

TICKERS = [
    ("copper", "HG=F", "LME Copper", "$/lb"),
    ("gold", "GC=F", "Gold", "$/oz"),
    ("wti", "CL=F", "WTI Crude", "$/bbl"),
    ("brent", "BZ=F", "Brent Crude", "$/bbl"),
    ("usdjpy", "JPY=X", "USD/JPY", "¥/$"),
]


def _round_value(value: float, key: str) -> float:
    if key == "copper":
        return round(value, 4)
    return round(value, 2)


def fetch_one(key: str, symbol: str, name: str, unit: str) -> dict:
    try:
        df = yf.Ticker(symbol).history(period="2y", interval="1d")
        if df is None or df.empty or "Close" not in df.columns:
            return {"error": "取得失敗"}

        df = df.sort_index()
        s = df["Close"].astype(float).dropna()
        if len(s) < 2:
            return {"error": "取得失敗"}

        current = float(s.iloc[-1])
        prev_close = float(s.iloc[-2])
        change_pct = (current - prev_close) / prev_close * 100.0

        week_ago = float(s.iloc[-6]) if len(s) >= 6 else float(s.iloc[0])
        month_ago = float(s.iloc[-22]) if len(s) >= 22 else float(s.iloc[0])

        ma20 = float(s.iloc[-20:].mean()) if len(s) >= 20 else float(s.mean())
        ma60 = float(s.iloc[-60:].mean()) if len(s) >= 60 else float(s.mean())

        history = []
        for idx, val in s.items():
            ts = pd.Timestamp(idx)
            history.append(
                {
                    "date": ts.strftime("%Y-%m-%d"),
                    "value": _round_value(float(val), key),
                }
            )

        return {
            "name": name,
            "unit": unit,
            "current": _round_value(current, key),
            "prev_close": _round_value(prev_close, key),
            "change_pct": round(change_pct, 2),
            "week_ago": _round_value(week_ago, key),
            "month_ago": _round_value(month_ago, key),
            "ma20": _round_value(ma20, key),
            "ma60": _round_value(ma60, key),
            "history": history,
        }
    except Exception:
        return {"error": "取得失敗"}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    commodities = {}
    for key, symbol, name, unit in TICKERS:
        commodities[key] = fetch_one(key, symbol, name, unit)

    payload = {
        "updated": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds"),
        "commodities": commodities,
    }

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
