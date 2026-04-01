"""
Tokyo Morning Brief Generator
------------------------------
毎朝の東京マーケットサマリーを自動生成するスクリプト。
GitHub Actionsで毎朝6:00 JSTに実行される。

使用API:
- yfinance: マーケットデータ取得
- Anthropic Claude API: コメンタリー生成
"""

import os
import json
import datetime
from pathlib import Path

import yfinance as yf
import anthropic


# ---------------------------------------------------------------------------
# 1. マーケットデータ取得
# ---------------------------------------------------------------------------

def fetch_market_data() -> dict:
    """前営業日のマーケットデータを取得"""

    data = {}

    # --- 日本株指数 ---
    jp_indices = {
        "日経225": "^N225",
        "TOPIX": "^TOPX",  # Note: yfinance may not always have TOPIX
    }

    # --- 米国株指数 ---
    us_indices = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "DOW": "^DJI",
    }

    # --- 為替 ---
    fx = {
        "USD/JPY": "USDJPY=X",
        "EUR/JPY": "EURJPY=X",
    }

    # --- コモディティ ---
    commodities = {
        "銅 (HG)": "HG=F",
        "原油 (WTI)": "CL=F",
        "金": "GC=F",
    }

    # --- VIX ---
    volatility = {
        "VIX": "^VIX",
    }

    # --- 素材セクター個別銘柄 ---
    materials_jp = {
        "日本製鉄 (5401)": "5401.T",
        "JFE HD (5411)": "5411.T",
        "神戸製鋼 (5406)": "5406.T",
        "信越化学 (4063)": "4063.T",
        "三井化学 (4183)": "4183.T",
        "住友化学 (4005)": "4005.T",
        "住友金属鉱山 (5713)": "5713.T",
        "三菱マテリアル (5711)": "5711.T",
    }

    materials_global = {
        "BHP": "BHP",
        "Rio Tinto": "RIO",
        "Vale": "VALE",
    }

    all_tickers = {}
    all_tickers.update(jp_indices)
    all_tickers.update(us_indices)
    all_tickers.update(fx)
    all_tickers.update(commodities)
    all_tickers.update(volatility)
    all_tickers.update(materials_jp)
    all_tickers.update(materials_global)

    # 全ティッカーを一括ダウンロード (直近5営業日分)
    symbols = list(all_tickers.values())
    try:
        raw = yf.download(symbols, period="5d", group_by="ticker", progress=False)
    except Exception as e:
        print(f"Warning: yfinance download failed: {e}")
        raw = None

    def extract_price_info(ticker_symbol: str, label: str) -> dict:
        """個別ティッカーの直近データを抽出"""
        try:
            if raw is not None and len(symbols) > 1:
                df = raw[ticker_symbol] if ticker_symbol in raw.columns.get_level_values(0) else None
            else:
                df = raw

            if df is None or df.empty:
                # フォールバック: 個別ダウンロード
                df = yf.download(ticker_symbol, period="5d", progress=False)

            if df is None or df.empty or len(df) < 2:
                return {"label": label, "ticker": ticker_symbol, "error": "データ取得不可"}

            latest = df.iloc[-1]
            prev = df.iloc[-2]

            close = float(latest["Close"])
            prev_close = float(prev["Close"])
            change = close - prev_close
            change_pct = (change / prev_close) * 100 if prev_close != 0 else 0

            return {
                "label": label,
                "ticker": ticker_symbol,
                "close": round(close, 2),
                "prev_close": round(prev_close, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
            }
        except Exception as e:
            return {"label": label, "ticker": ticker_symbol, "error": str(e)}

    # カテゴリ別にデータ整理
    data["jp_indices"] = [extract_price_info(v, k) for k, v in jp_indices.items()]
    data["us_indices"] = [extract_price_info(v, k) for k, v in us_indices.items()]
    data["fx"] = [extract_price_info(v, k) for k, v in fx.items()]
    data["commodities"] = [extract_price_info(v, k) for k, v in commodities.items()]
    data["volatility"] = [extract_price_info(v, k) for k, v in volatility.items()]
    data["materials_jp"] = [extract_price_info(v, k) for k, v in materials_jp.items()]
    data["materials_global"] = [extract_price_info(v, k) for k, v in materials_global.items()]

    return data


# ---------------------------------------------------------------------------
# 2. Claude APIでコメンタリー生成
# ---------------------------------------------------------------------------

def generate_commentary(market_data: dict) -> str:
    """Claude APIを使ってMorning Briefコメンタリーを生成"""

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 環境変数を自動読み込み

    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    weekdays_jp = ["月", "火", "水", "木", "金", "土", "日"]
    date_str = today.strftime("%Y年%m月%d日") + f"（{weekdays_jp[today.weekday()]}）"

    data_json = json.dumps(market_data, ensure_ascii=False, indent=2)

    prompt = f"""あなたはヘッジファンドの素材セクター専門シニアアナリストです。
以下のマーケットデータを基に、プロフェッショナルなMorning Briefを作成してください。

## マーケットデータ
{data_json}

## 出力フォーマット（Markdown）

# Tokyo Morning Brief - {date_str}

## マーケット全体感
（3-5文で前日の東京市場の動きを要約。何が主要ドライバーだったか、売買代金の水準感、外国人投資家のフロー感など。データから読み取れる範囲で分析的に。）

## 主要指数
| 指数 | 終値 | 前日比 | 変動率 |
|------|------|--------|--------|
（jp_indicesのデータをテーブルに。データ取得不可の場合はN/Aと記載）

## 米国・グローバル市場（オーバーナイト）
（us_indices, fx, volatilityのデータを基に、米国市場の動き、為替、VIXについて簡潔に2-3文で。）

## コモディティ
| 商品 | 価格 | 前日比 |
|------|------|--------|
（commoditiesのデータをテーブルに）

## 素材セクター注目点
### 鉄鋼
（日本製鉄、JFE、神戸製鋼の動きとコメント）
### 化学
（信越化学、三井化学、住友化学の動きとコメント）
### 非鉄金属
（住友金属鉱山、三菱マテリアルの動きとコメント）
### グローバル素材
（BHP、RIO、VALEの動きとコメント）

## トレーディングシグナル
（市場のセンチメント、テクニカルの節目、注意すべきリスク要因を簡潔に3-5ポイントで）

---
*Generated by CEO Fund Research | Powered by Claude API*

## 注意事項
- データが「error」や「データ取得不可」の場合は「N/A」と表示し、利用可能なデータで最善の分析を行うこと
- 投資助言ではなく事実に基づくリサーチコメンタリーであること
- 日本語で、簡潔かつプロフェッショナルなトーンで書くこと
- 数値は必ずマーケットデータから引用し、推測で数値を作らないこと
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


# ---------------------------------------------------------------------------
# 3. ファイル保存
# ---------------------------------------------------------------------------

def save_brief(content: str, output_dir: str = "briefs") -> str:
    """Morning Briefをマークダウンファイルとして保存"""

    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    filename = f"morning-brief-{today.strftime('%Y-%m-%d')}.md"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filepath = output_path / filename
    filepath.write_text(content, encoding="utf-8")

    print(f"Saved: {filepath}")
    return str(filepath)


# ---------------------------------------------------------------------------
# メイン実行
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Tokyo Morning Brief Generator")
    print("=" * 60)

    # 1. データ取得
    print("\n[1/3] Fetching market data...")
    market_data = fetch_market_data()
    print(f"  - JP indices: {len(market_data['jp_indices'])} items")
    print(f"  - US indices: {len(market_data['us_indices'])} items")
    print(f"  - Materials JP: {len(market_data['materials_jp'])} items")

    # 2. コメンタリー生成
    print("\n[2/3] Generating commentary with Claude API...")
    commentary = generate_commentary(market_data)
    print(f"  - Generated {len(commentary)} characters")

    # 3. 保存
    print("\n[3/3] Saving brief...")
    output_dir = os.environ.get("OUTPUT_DIR", "briefs")
    filepath = save_brief(commentary, output_dir)

    print(f"\nDone! Brief saved to: {filepath}")
    print("=" * 60)


if __name__ == "__main__":
    main()
