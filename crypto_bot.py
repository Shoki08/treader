import requests
import json
import os
import time
import datetime
import pandas as pd

# ==========================================
# 設定
# ==========================================
DATA_DIR = "docs/data"
os.makedirs(DATA_DIR, exist_ok=True)

# コインチェック取扱 35銘柄 (2024/2025時点想定)
# CoinGeckoのIDと対応付け
COINS = {
    "BTC": "bitcoin", "ETH": "ethereum", "ETC": "ethereum-classic",
    "LSK": "lisk", "XRP": "ripple", "XEM": "nem",
    "LTC": "litecoin", "BCH": "bitcoin-cash", "MONA": "monacoin",
    "XLM": "stellar", "QTUM": "qtum", "BAT": "basic-attention-token",
    "IOST": "iost", "ENJ": "enjincoin", "SAND": "the-sandbox",
    "DOT": "polkadot", "CHZ": "chiliz", "LINK": "chainlink",
    "MATIC": "matic-network", "ASTR": "astar", "FLR": "flare-networks",
    "APE": "apecoin", "AXS": "axie-infinity", "SHIB": "shiba-inu",
    "AVAX": "avalanche-2", "WBTC": "wrapped-bitcoin", "DAI": "dai",
    "MKR": "maker", "IMX": "immutable-x", "RNDR": "render-token",
    "FNCT": "financie-token", "BRIL": "brilliance", "JASMY": "jasmycoin",
    "OMG": "omisego", "PLT": "palette-token"
}

class CryptoAnalyzer:
    def __init__(self):
        # 日本時間
        self.now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
        self.date_str = self.now.strftime("%Y/%m/%d %H:%M")
        self.results = {}

    def fetch_ohlc(self, coin_id, days):
        """
        CoinGeckoから価格データを取得
        days=1 -> 30分足 (短期用)
        days=90 -> 日足 (長期用)
        """
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=jpy&days={days}"
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            # [Time, Open, High, Low, Close]
            df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close"])
            return df
        except Exception as e:
            print(f"Error fetching {coin_id} (days={days}): {e}")
            return None

    def calculate_rsi(self, df, period=14):
        if len(df) < period: return 50.0
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        return df["rsi"].iloc[-1]

    def get_signal(self, rsi):
        # 初心者向けにわかりやすい言葉にする
        if rsi <= 30:
            return "買いチャンス", "#eb4d3d", "安値圏です" # 赤
        elif rsi >= 70:
            return "売り検討", "#06c755", "高値圏です" # 緑(LINEカラー)
        elif rsi >= 55:
             return "上昇中", "#f1c40f", "トレンド継続"
        else:
            return "様子見", "#95a5a6", "方向感なし"

    def analyze_coin(self, symbol, coin_id):
        print(f"Analyzing {symbol}...")
        
        # 1. 短期分析 (デイトレード視点: 30分足)
        df_short = self.fetch_ohlc(coin_id, days=1)
        short_res = {"rsi": 50, "signal": "---", "color": "#ccc", "msg": "取得失敗"}
        current_price = 0
        
        if df_short is not None and not df_short.empty:
            current_price = float(df_short["close"].iloc[-1])
            rsi_s = self.calculate_rsi(df_short)
            sig, col, msg = self.get_signal(rsi_s)
            short_res = {"rsi": round(rsi_s, 1), "signal": sig, "color": col, "msg": msg}
            time.sleep(1.5) # API制限回避

        # 2. 長期分析 (スイング/ガチホ視点: 日足)
        df_long = self.fetch_ohlc(coin_id, days=90)
        long_res = {"rsi": 50, "signal": "---", "color": "#ccc", "msg": "取得失敗"}
        
        if df_long is not None and not df_long.empty:
            rsi_l = self.calculate_rsi(df_long)
            sig, col, msg = self.get_signal(rsi_l)
            long_res = {"rsi": round(rsi_l, 1), "signal": sig, "color": col, "msg": msg}
            time.sleep(1.5) # API制限回避

        return {
            "symbol": symbol,
            "id": coin_id,
            "price": current_price,
            "short": short_res,
            "long": long_res
        }

    def run(self):
        print("Starting Full Analysis (Short & Long)...")
        for symbol, coin_id in COINS.items():
            res = self.analyze_coin(symbol, coin_id)
            self.results[symbol] = res
        
        output = {
            "updated": self.date_str,
            "data": self.results
        }
        with open(f"{DATA_DIR}/crypto_signal.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print("Analysis Complete.")

if __name__ == "__main__":
    CryptoAnalyzer().run()
