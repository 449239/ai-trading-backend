from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import BollingerBands, AverageTrueRange
from datetime import datetime
import plotly.graph_objs as go

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

preferences = {}

@app.get("/api/set-preference")
def set_preference(key: str, value: str):
    preferences[key] = value.lower() == "true"
    return {"status": "ok", "key": key, "value": preferences[key]}

@app.get("/api/signal")
def get_signal(ticker: str = "AAPL", strategy: str = "Scalping"):
    df = yf.download(ticker, period="5d", interval="15m")
    df.dropna(inplace=True)

    df["RSI"] = RSIIndicator(df["Close"]).rsi()
    df["EMA"] = EMAIndicator(df["Close"]).ema_indicator()
    df["MACD"] = MACD(df["Close"]).macd()
    bb = BollingerBands(df["Close"])
    df["BB_high"] = bb.bollinger_hband()
    df["BB_low"] = bb.bollinger_lband()
    df["ATR"] = AverageTrueRange(df["High"], df["Low"], df["Close"]).average_true_range()

    close = df["Close"].iloc[-1]
    ema = df["EMA"].iloc[-1]
    rsi = df["RSI"].iloc[-1]
    macd_val = df["MACD"].iloc[-1]
    bb_high = df["BB_high"].iloc[-1]
    bb_low = df["BB_low"].iloc[-1]

    signal, reason = "HOLD", "Neutral"

    if strategy == "Scalping":
        if rsi < 30 and close < ema:
            signal, reason = "BUY", "Oversold + below EMA"
        elif rsi > 70 and close > ema:
            signal, reason = "SELL", "Overbought + above EMA"
    elif strategy == "Swing Trading":
        if macd_val > 0 and close > ema:
            signal, reason = "BUY", "MACD bullish + above EMA"
        elif macd_val < 0 and close < ema:
            signal, reason = "SELL", "MACD bearish + below EMA"
    elif strategy == "Breakout":
        if close > bb_high:
            signal, reason = "BUY", "Price broke above Bollinger Band"
        elif close < bb_low:
            signal, reason = "SELL", "Price broke below Bollinger Band"

    support = df["Low"].rolling(10).min().iloc[-1]
    resistance = df["High"].rolling(10).max().iloc[-1]

    return {
        "signal": signal,
        "confidence": round(100 - abs(rsi - 50), 2),
        "sentiment": "Bullish" if signal == "BUY" else "Bearish" if signal == "SELL" else "Neutral",
        "entry": round(close, 2),
        "stop": round(close * 0.98, 2),
        "take": round(close * 1.02, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/chart")
def get_chart(ticker: str, theme: str = "dark", showVolume: bool = False, candleStyle: str = "standard"):
    df = yf.download(ticker, period="5d", interval="15m")
    df.reset_index(inplace=True)

    candle = go.Candlestick(
        x=df["Datetime"],
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color='green',
        decreasing_line_color='red'
    )

    layout = go.Layout(
        template="plotly_dark" if theme == "dark" else "plotly_white",
        xaxis=dict(title="Time"), yaxis=dict(title="Price"),
        height=500, margin=dict(l=40, r=40, t=40, b=40)
    )

    fig = go.Figure(data=[candle], layout=layout)

    if preferences.get("show_volume", False) and showVolume:
        fig.add_trace(go.Bar(x=df["Datetime"], y=df["Volume"], name="Volume", yaxis="y2"))

    return fig.to_html(full_html=False)
