import requests
import json
import os
import time
import datetime
import pandas as pd
import numpy as np

DATA_DIR = "docs/data"
os.makedirs(DATA_DIR, exist_ok=True)

COINS = {
    "BTC": "bitcoin", "ETH": "ethereum", "XRP": "ripple",
    "XEM": "nem", "LTC": "litecoin", "BCH": "bitcoin-cash",
    "MONA": "monacoin", "XLM": "stellar", "QTUM": "qtum",
    "BAT": "basic-attention-token", "IOST": "iost", "ENJ": "enjincoin",
    "SAND": "the-sandbox", "DOT": "polkadot", "CHZ": "chiliz",
    "LINK": "chainlink", "MATIC": "matic-network", "ASTR": "astar",
    "APE": "apecoin", "AXS": "axie-infinity", "SHIB": "shiba-inu",
    "AVAX": "avalanche-2", "JASMY": "jasmycoin", "OMG": "omisego",
    "PLT": "palette-token", "FNCT": "financie-token", "DAI": "dai",
    "MKR": "maker"
}

class CryptoHedgeFundAnalyzer:
    def __init__(self):
        self.now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
        self.date_str = self.now.strftime("%Y/%m/%d %H:%M")
        self.results = {}
        self.btc_trend = "NEUTRAL"

    def fetch_ohlc(self, coin_id, days):
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=jpy&days={days}"
        for _ in range(3):
            try:
                resp = requests.get(url, timeout=30)
                if resp.status_code == 429:
                    time.sleep(10)
                    continue
                resp.raise_for_status()
                data = resp.json()
                if not data: return None
                df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close"])
                return df
            except: time.sleep(2)
        return None

    def fetch_fear_and_greed(self):
        try:
            r = requests.get("https://api.alternative.me/fng/", timeout=10)
            return int(r.json()['data'][0]['value'])
        except: return 50

    def calc_indicators(self, df):
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        sma20 = df["close"].rolling(20).mean()
        std20 = df["close"].rolling(20).std()
        bb_up = sma20 + (std20 * 2)
        bb_low = sma20 - (std20 * 2)

        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()
        macd = ema12 - ema26
        sig = macd.ewm(span=9).mean()

        ma7 = df["close"].rolling(7).mean()
        ma25 = df["close"].rolling(25).mean()
        ma99 = df["close"].rolling(99).mean()

        prev_close = df["close"].shift(1)
        tr = pd.concat([df["high"]-df["low"], (df["high"]-prev_close).abs(), (df["low"]-prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()

        return rsi, bb_up, bb_low, macd, sig, ma7, ma25, ma99, atr

    def analyze_logic(self, df, timeframe_name):
        # データ不足時の処理
        if df is None or len(df) < 100:
            return {"score":0, "signal":"---", "color":"#ccc", "msg":"データ不足", "reasons":[], "price":0}

        price = df["close"].iloc[-1]
        rsi, bb_u, bb_l, macd, sig, ma7, ma25, ma99, atr = self.calc_indicators(df)
        
        _rsi = rsi.iloc[-1]
        _macd = macd.iloc[-1]
        _sig = sig.iloc[-1]
        _atr = atr.iloc[-1]

        score = 50
        reasons = [] # 採点理由リスト

        # 1. RSI
        if _rsi <= 30:
            score += 15
            reasons.append(f"RSI底値圏({int(_rsi)})")
        elif _rsi >= 70:
            score -= 15
            reasons.append(f"RSI過熱気味({int(_rsi)})")

        # 2. ボリンジャーバンド
        if price <= bb_l.iloc[-1]:
            score += 10
            reasons.append("バンド下限タッチ")
        elif price >= bb_u.iloc[-1]:
            score -= 10
            reasons.append("バンド上限タッチ")

        # 3. MACD
        if _macd > _sig:
            score += 10
            reasons.append("上昇トレンド中")
        else:
            score -= 10

        # 4. 移動平均線 (Perfect Order)
        if price > ma7.iloc[-1] > ma25.iloc[-1] > ma99.iloc[-1]:
            score += 25
            reasons.append("パーフェクトオーダー")
        elif price < ma7.iloc[-1] < ma25.iloc[-1] < ma99.iloc[-1]:
            score -= 25
            reasons.append("下落トレンド継続")

        # 5. 全体相場補正
        if self.btc_trend == "DOWN" and score > 50:
            score -= 15
            reasons.append("BTC軟調により割引")
        elif self.btc_trend == "UP" and score > 50:
            score += 5
            reasons.append("BTC好調ボーナス")

        score = max(0, min(100, int(score)))
        
        # 出口戦略
        sl_price = int(price - (_atr * 2))
        tp_price = int(price + (_atr * 3))

        # 評価メッセージ
        signal, color, msg = "様子見", "#95a5a6", "方向感なし"
        if score >= 85: signal, color, msg = "激アツ", "#eb4d3d", "全指標が好転！"
        elif score >= 65: signal, color, msg = "買い", "#e67e22", "上昇期待大"
        elif score <= 20: signal, color, msg = "暴落警戒", "#8e44ad", "底抜けの危険"
        elif score <= 35: signal, color, msg = "売り", "#06c755", "利益確定を推奨"

        # 理由がなければデフォルトを入れる
        if not reasons: reasons.append("特筆事項なし")

        return {
            "score": score, "signal": signal, "color": color, "msg": msg,
            "reasons": reasons, # ここに追加！
            "price": price, "tp": tp_price, "sl": sl_price
        }

    def determine_btc_trend(self):
        df = self.fetch_ohlc("bitcoin", 90)
        if df is None: return
        ma25 = df["close"].rolling(25).mean().iloc[-1]
        self.btc_trend = "UP" if df["close"].iloc[-1] > ma25 else "DOWN"

    def run(self):
        print("Starting HEDGE FUND Analysis...")
        self.determine_btc_trend()
        fng = self.fetch_fear_and_greed()
        
        market_info = {"btc_trend": self.btc_trend, "fng_score": fng}

        for symbol, coin_id in COINS.items():
            print(f"Analyzing {symbol}...")
            df_s = self.fetch_ohlc(coin_id, 1)
            res_s = self.analyze_logic(df_s, "short")
            time.sleep(5)
            
            df_l = self.fetch_ohlc(coin_id, 90)
            res_l = self.analyze_logic(df_l, "long")
            time.sleep(5)

            self.results[symbol] = {
                "symbol": symbol, "price": res_s["price"],
                "short": res_s, "long": res_l
            }

        output = {"updated": self.date_str, "market": market_info, "data": self.results}
        with open(f"{DATA_DIR}/crypto_signal.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print("Done.")

if __name__ == "__main__":
    CryptoHedgeFundAnalyzer().run()