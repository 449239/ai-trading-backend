from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_preferences = {}
trade_log = []

@app.get("/api/set-preference")
def set_preference(key: str, value: str):
    user_preferences[key] = value.lower() == "true"
    return {"status": "updated", "preferences": user_preferences}

@app.get("/api/signal")
def get_signal(ticker: str, strategy: str = "Swing Trading"):
    data = yf.download(ticker, period="5d", interval="15m")
    data.dropna(inplace=True)

    data['EMA20'] = data['Close'].ewm(span=20).mean()
    data['EMA50'] = data['Close'].ewm(span=50).mean()
    data['RSI'] = 100 - (100 / (1 + data['Close'].pct_change().rolling(window=14).mean()))
    data['MACD'] = data['EMA20'] - data['EMA50']
    latest = data.iloc[-1]

    signal = "BUY" if latest['MACD'] > 0 and latest['RSI'] < 70 else "SELL"
    confidence = 85 if signal == "BUY" else 70
    entry_price = round(latest['Close'], 2)
    stop = round(entry_price * 0.98, 2)
    take = round(entry_price * 1.02, 2)
    support = round(data['Low'].rolling(window=20).min().iloc[-1], 2)
    resistance = round(data['High'].rolling(window=20).max().iloc[-1], 2)

    gaps = []
    for i in range(1, len(data)):
        if abs(data['Open'].iloc[i] - data['Close'].iloc[i - 1]) > data['Close'].std():
            gaps.append({
                "time": data.index[i].strftime('%Y-%m-%d %H:%M'),
                "price": data['Open'].iloc[i],
                "type": "gap"
            })

    trade = {
        "signal": signal,
        "entry": entry_price,
        "confidence": confidence,
        "sentiment": "Bullish" if signal == "BUY" else "Bearish",
        "stop": stop,
        "take": take,
        "support": support,
        "resistance": resistance,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "reason": f"MACD: {round(latest['MACD'],2)}, RSI: {round(latest['RSI'],2)}",
        "gaps": gaps,
        "PnL_dollars": 0,
        "PnL_percent": 0
    }

    trade_log.append(trade)
    if len(trade_log) > 100:
        trade_log.pop(0)

    return trade

@app.get("/api/trades")
def get_trade_history():
    return {"history": trade_log}

@app.get("/api/chart")
def get_chart(ticker: str, theme: str = "dark", showVolume: bool = True, candleStyle: str = "standard"):
    df = yf.download(ticker, period="5d", interval="15m")
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        name="Candles"
    )])
    fig.update_layout(
        template="plotly_dark" if theme == "dark" else "plotly_white",
        margin=dict(t=20, b=20),
        height=500,
    )
    if showVolume:
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", yaxis="y2"))

    return fig.to_html(include_plotlyjs='cdn')

